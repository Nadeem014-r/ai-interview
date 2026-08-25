from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Source, Document, DocumentChunk, Company, Role
from app.research.crawler import (
    CompanyResearchCrawler,
    CrawlerError,
    ResearchSecurityError
)
from app.rag.chunker import DocumentChunker
from app.rag.vector_store import VectorStore

logger = logging.getLogger("ai_interviewer.research.pipeline")

class PipelineError(Exception):
    """Base exception for research pipeline errors."""
    pass

class StaleRefreshFailedError(PipelineError):
    """Raised when refreshing a stale source fails, while preserving existing valid data."""
    def __init__(self, source_id: int, original_error: Exception):
        super().__init__(f"Failed to refresh stale source #{source_id}: {original_error}")
        self.source_id = source_id
        self.original_error = original_error

class ResearchPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore(db)

    async def get_existing_source(
        self,
        company_id: Optional[int],
        role_id: Optional[int],
        source_url: str
    ) -> Optional[Source]:
        """Find an existing Source record by company_id, role_id, and source_url."""
        stmt = select(Source).options(
            selectinload(Source.documents).selectinload(Document.chunks)
        ).where(
            Source.source_url == source_url
        )
        if company_id:
            stmt = stmt.where(Source.company_id == company_id)
        if role_id:
            stmt = stmt.where(Source.role_id == role_id)
            
        result = await self.db.execute(stmt)
        return result.scalars().first()

    def is_source_fresh(self, source: Source, freshness_hours: Optional[int] = None) -> bool:
        """Check if a source was fetched within the freshness duration."""
        if not source.fetched_at:
            return False
            
        hours = freshness_hours if freshness_hours is not None else settings.RESEARCH_FRESHNESS_HOURS
        max_age = timedelta(hours=hours)
        age = datetime.utcnow() - source.fetched_at
        return age <= max_age

    async def ingest_company_role_research(
        self,
        company_id: int,
        role_id: int,
        source_url: str,
        title: Optional[str] = None,
        allowed_domains: Optional[List[str]] = None,
        force_refresh: bool = False,
        freshness_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Complete research ingestion flow with:
        1. SSRF and Domain security validation
        2. Deduplication and freshness caching
        3. Stale data safe refresh (preserves valid data on network failure)
        4. Real HTML cleaning (BeautifulSoup) and SHA-256 content hashing
        5. Full provenance metadata tracking in vector chunks
        6. Transactional persistence
        """
        # Step 1: Check existing source for deduplication / caching
        existing_source = await self.get_existing_source(company_id, role_id, source_url)

        if existing_source and not force_refresh:
            if self.is_source_fresh(existing_source, freshness_hours):
                logger.info(f"Cache hit: Reusing fresh research source #{existing_source.id} for {source_url}")
                doc = existing_source.documents[0] if existing_source.documents else None
                return {
                    "source": existing_source,
                    "document": doc,
                    "is_cached": True,
                    "status": "fresh_cached",
                    "content_hash": existing_source.content_hash,
                    "chunks_count": len(doc.chunks) if doc and hasattr(doc, "chunks") and doc.chunks else 0
                }

        # Step 2: Fetch and clean external content
        try:
            crawl_res = await CompanyResearchCrawler.fetch_page_content(
                url=source_url,
                allowed_domains=allowed_domains
            )
        except Exception as fetch_err:
            if existing_source:
                # Keep last known valid content intact on refresh failure
                logger.warning(
                    f"Refetch failed for stale source #{existing_source.id} ({source_url}). "
                    f"Preserving existing valid content. Error: {fetch_err}"
                )
                raise StaleRefreshFailedError(existing_source.id, fetch_err) from fetch_err
            raise fetch_err

        cleaned_text = crawl_res["cleaned_text"]
        new_content_hash = crawl_res["content_hash"]
        doc_title = title or crawl_res.get("title") or f"Research: {source_url}"
        extraction_method = crawl_res.get("extraction_method", "beautifulsoup4")

        # Step 3: Check if content is unchanged on refetch
        if existing_source and existing_source.content_hash == new_content_hash:
            logger.info(f"Content unchanged for source #{existing_source.id}. Updating fetched timestamp.")
            doc = existing_source.documents[0] if existing_source.documents else None
            chunks_count = len(doc.chunks) if doc and hasattr(doc, "chunks") and doc.chunks else 0
            existing_source.fetched_at = datetime.utcnow()
            await self.db.commit()
            return {
                "source": existing_source,
                "document": doc,
                "is_cached": True,
                "status": "unchanged_refreshed",
                "content_hash": new_content_hash,
                "chunks_count": chunks_count
            }

        # Step 4: Transactional Persistence & Provenance Chunking
        try:
            if existing_source:
                # Update existing source & document
                source = existing_source
                source.title = doc_title
                source.content_hash = new_content_hash
                source.fetched_at = datetime.utcnow()
                
                stmt_doc = select(Document).where(Document.source_id == source.id)
                res_doc = await self.db.execute(stmt_doc)
                doc = res_doc.scalars().first()
                if doc:
                    doc.title = doc_title
                    doc.content = cleaned_text
                    # Clear previous chunks to avoid stale index fragments
                    await self.vector_store.delete_document_chunks(doc.id)
                else:
                    doc = Document(source_id=source.id, title=doc_title, content=cleaned_text)
                    self.db.add(doc)

                await self.db.commit()
                await self.db.refresh(source)
                await self.db.refresh(doc)
            else:
                # Create new source
                source = Source(
                    company_id=company_id,
                    role_id=role_id,
                    source_type="official_job_desc",
                    source_url=source_url,
                    title=doc_title,
                    content_hash=new_content_hash,
                    trust_level="official_trusted",
                    fetched_at=datetime.utcnow()
                )
                self.db.add(source)
                await self.db.commit()
                await self.db.refresh(source)

                # Create document
                doc = Document(
                    source_id=source.id,
                    title=doc_title,
                    content=cleaned_text
                )
                self.db.add(doc)
                await self.db.commit()
                await self.db.refresh(doc)

            # Step 5: Chunk and Index with Rich Provenance Metadata
            chunks = DocumentChunker.chunk_text(cleaned_text, chunk_size=200, overlap=30)
            for idx, chunk_text in enumerate(chunks):
                provenance_meta = {
                    "company_id": company_id,
                    "role_id": role_id,
                    "source_id": source.id,
                    "document_id": doc.id,
                    "source_url": source_url,
                    "source_title": doc_title,
                    "content_hash": new_content_hash,
                    "chunk_index": idx,
                    "extraction_method": extraction_method,
                    "fetched_at": source.fetched_at.isoformat() if source.fetched_at else datetime.utcnow().isoformat()
                }
                await self.vector_store.add_chunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    chunk_text=chunk_text,
                    metadata=provenance_meta
                )

            logger.info(f"Ingested {len(chunks)} chunks for source #{source.id} ({doc_title})")
            return {
                "source": source,
                "document": doc,
                "is_cached": False,
                "status": "ingested_new" if not existing_source else "updated_content",
                "content_hash": new_content_hash,
                "chunks_count": len(chunks)
            }

        except Exception as db_err:
            await self.db.rollback()
            logger.error(f"Database error during research ingestion: {db_err}", exc_info=True)
            raise db_err
