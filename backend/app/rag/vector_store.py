"""Phase 7: Vector Store Implementation.

Provides robust JSON-based embedding persistence, metadata pre-filtering,
cosine similarity ranking, deterministic tie-breaking, and rich provenance tracking.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.db.models import DocumentChunk, Document, Source
from app.ai.factory import AIFactory
from app.ai.base import EmbeddingProvider
from app.rag.similarity import cosine_similarity, validate_vector
from app.rag.exceptions import (
    VectorStoreError,
    EmbeddingValidationError,
    EmbeddingProviderError,
    InvalidVectorError,
)

logger = logging.getLogger("ai_interviewer.rag.vector_store")


class VectorStore:
    """Production vector store managing document chunk embeddings and similarity search."""

    def __init__(self, db: AsyncSession, embedder: Optional[EmbeddingProvider] = None):
        self.db = db
        self.embedder = embedder or AIFactory.get_embedding_provider()

    def _validate_embedding(self, vec: Any) -> List[float]:
        """Validate embedding structure, non-emptiness, and numeric validity."""
        try:
            return validate_vector(vec, allow_empty=False)
        except InvalidVectorError as e:
            raise EmbeddingValidationError(f"Embedding validation failed: {e}") from e

    async def add_chunk(
        self,
        document_id: int,
        chunk_index: int,
        chunk_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> DocumentChunk:
        """
        Persist a single document chunk along with its validated vector embedding and metadata.
        """
        if not chunk_text or not chunk_text.strip():
            raise VectorStoreError("chunk_text cannot be empty.")

        try:
            if embedding is None:
                try:
                    raw_emb = await self.embedder.embed_text(chunk_text)
                except Exception as emb_err:
                    raise EmbeddingProviderError(f"Embedding provider failure: {emb_err}") from emb_err
                validated_emb = self._validate_embedding(raw_emb)
            else:
                validated_emb = self._validate_embedding(embedding)

            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                chunk_text=chunk_text.strip(),
                metadata_json=metadata or {},
                embedding_json=validated_emb
            )
            self.db.add(chunk)
            await self.db.commit()
            await self.db.refresh(chunk)
            return chunk

        except (EmbeddingValidationError, EmbeddingProviderError):
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to persist document chunk: {exc}", exc_info=True)
            raise VectorStoreError(f"Database error persisting chunk: {exc}") from exc

    async def add_chunks_batch(
        self,
        chunks_data: List[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """
        Persist multiple chunks in a single transaction with batch embedding generation.
        """
        if not chunks_data:
            return []

        try:
            texts_to_embed = []
            needs_embedding_indices = []
            
            for idx, c in enumerate(chunks_data):
                if not c.get("chunk_text", "").strip():
                    raise VectorStoreError(f"Chunk at index {idx} has empty chunk_text.")
                if "embedding" not in c or c["embedding"] is None:
                    texts_to_embed.append(c["chunk_text"])
                    needs_embedding_indices.append(idx)

            if texts_to_embed:
                try:
                    generated_embeddings = await self.embedder.embed_batch(texts_to_embed)
                except Exception as emb_err:
                    raise EmbeddingProviderError(f"Batch embedding generation failed: {emb_err}") from emb_err

                for text_idx, orig_idx in enumerate(needs_embedding_indices):
                    chunks_data[orig_idx]["embedding"] = generated_embeddings[text_idx]

            created_chunks: List[DocumentChunk] = []
            for c in chunks_data:
                val_emb = self._validate_embedding(c["embedding"])
                chunk = DocumentChunk(
                    document_id=c["document_id"],
                    chunk_index=c["chunk_index"],
                    chunk_text=c["chunk_text"].strip(),
                    metadata_json=c.get("metadata", {}),
                    embedding_json=val_emb
                )
                self.db.add(chunk)
                created_chunks.append(chunk)

            await self.db.commit()
            for chunk in created_chunks:
                await self.db.refresh(chunk)
            return created_chunks

        except (EmbeddingValidationError, EmbeddingProviderError):
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed in add_chunks_batch: {exc}", exc_info=True)
            raise VectorStoreError(f"Database error during batch chunk insert: {exc}") from exc

    async def delete_document_chunks(self, document_id: int) -> int:
        """Delete all vector chunks for a specific document."""
        try:
            stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            result = await self.db.execute(stmt)
            await self.db.commit()
            return result.rowcount
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to delete chunks for doc #{document_id}: {exc}", exc_info=True)
            raise VectorStoreError(f"Database error deleting document chunks: {exc}") from exc

    async def similarity_search(
        self,
        query: str,
        company_id: Optional[int] = None,
        role_id: Optional[int] = None,
        source_id: Optional[int] = None,
        document_id: Optional[int] = None,
        trust_level: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 3,
        min_similarity: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute similarity search with metadata pre-filtering, similarity thresholding,
        and deterministic tie-breaking.
        """
        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        # Bound top_k to sensible ceiling
        effective_top_k = min(top_k, 50)

        # 1. Build metadata-filtered query joining Document and Source
        stmt = (
            select(DocumentChunk, Document, Source)
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(Source, Document.source_id == Source.id)
        )

        if company_id is not None:
            stmt = stmt.where(Source.company_id == company_id)
        if role_id is not None:
            stmt = stmt.where(Source.role_id == role_id)
        if source_id is not None:
            stmt = stmt.where(Source.id == source_id)
        if document_id is not None:
            stmt = stmt.where(Document.id == document_id)
        if trust_level is not None:
            stmt = stmt.where(Source.trust_level == trust_level)
        if source_type is not None:
            stmt = stmt.where(Source.source_type == source_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        # 2. Generate the query embedding -- only once there is something to
        #    score it against. Embedding first meant every retrieval on a
        #    deployment with an empty or unmatched corpus (no document has been
        #    ingested for this company/role) paid a provider embedding call for
        #    a result that could only ever be empty. Question generation calls
        #    this on every interview turn, so that was a per-turn charge for
        #    nothing. When rows exist the behaviour is unchanged.
        if not rows:
            return []

        try:
            raw_query_vector = await self.embedder.embed_text(query.strip())
        except Exception as emb_err:
            raise EmbeddingProviderError(f"Query embedding generation failed: {emb_err}") from emb_err

        query_vector = self._validate_embedding(raw_query_vector)

        scored_chunks: List[Dict[str, Any]] = []
        for chunk, doc, source in rows:
            if not chunk.embedding_json:
                continue

            sim = cosine_similarity(query_vector, chunk.embedding_json, raise_on_error=False)

            if min_similarity is not None and sim < min_similarity:
                continue

            scored_chunks.append({
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "source_id": source.id,
                "company_id": source.company_id,
                "role_id": source.role_id,
                "source_url": source.source_url,
                "source_title": source.title,
                "content_hash": source.content_hash,
                "trust_level": source.trust_level,
                "source_type": source.source_type,
                "chunk_index": chunk.chunk_index,
                "text": chunk.chunk_text,
                "metadata": chunk.metadata_json or {},
                "similarity": sim
            })

        # 3. Deterministic Sorting:
        # Highest similarity first; tie-break deterministically by (document_id, chunk_index, chunk_id)
        scored_chunks.sort(
            key=lambda x: (-x["similarity"], x["document_id"], x["chunk_index"], x["chunk_id"])
        )

        return scored_chunks[:effective_top_k]
