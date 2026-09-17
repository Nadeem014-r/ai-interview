from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from app.core.database import get_db
from app.core.security import require_role
from app.db.models import Company, Role
from app.schemas.interview import ResearchCompanyRequest
from app.research.pipeline import ResearchPipeline, StaleRefreshFailedError
from app.research.security import (
    ResearchSecurityError,
    InvalidURLError,
    SSRFProtectionError,
    DisallowedDomainError
)
from app.research.crawler import (
    CrawlerError,
    UnsupportedContentTypeError,
    OversizedContentError,
    EmptyContentError,
    FetchTimeoutError,
    HTTPFetchError
)

logger = logging.getLogger("ai_interviewer.api.research")

router = APIRouter(prefix="/research", tags=["Company Research & RAG Ingestion"])

@router.post("/company", status_code=status.HTTP_200_OK)
async def trigger_company_research(
    req: ResearchCompanyRequest,
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    if not req.company_name or not req.company_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_name cannot be blank.")
    if not req.role_title or not req.role_title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_title cannot be blank.")
    # Only a real, operator-supplied page is ingested. A guessed careers URL is
    # not a source: at best it fails, at worst it indexes an unrelated page.
    if not req.source_url or not req.source_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_url is required.")

    # 1. Lookup or create company
    stmt_c = select(Company).where(Company.name.ilike(f"%{req.company_name.strip()}%"))
    res_c = await db.execute(stmt_c)
    company = res_c.scalars().first()
    if not company:
        company = Company(
            name=req.company_name.strip(),
            slug=req.company_name.strip().lower().replace(" ", "-"),
            description=f"Catalog company profile for {req.company_name.strip()}"
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)

    # 2. Lookup or create role. Exact (case-insensitive) title match only: a
    # substring match attached "Software Engineer" sources to whichever
    # specialised role happened to come first, e.g. "Software Engineer (Backend)".
    stmt_r = select(Role).where(
        Role.company_id == company.id,
        func.lower(func.trim(Role.title)) == req.role_title.strip().lower()
    ).order_by(Role.id)
    res_r = await db.execute(stmt_r)
    role = res_r.scalars().first()
    if not role:
        role = Role(
            company_id=company.id,
            title=req.role_title.strip(),
            level="Entry / L3",
            required_skills=["Software Engineering"],
            key_topics=["Computer Science"]
        )
        db.add(role)
        await db.commit()
        await db.refresh(role)

    url = req.source_url.strip()

    # 3. Execute Research Ingestion Pipeline
    pipeline = ResearchPipeline(db)
    try:
        result = await pipeline.ingest_company_role_research(
            company_id=company.id,
            role_id=role.id,
            source_url=url,
            title=f"{company.name} - {role.title} Official Specs"
        )
        source = result["source"]
        doc = result.get("document")
        return {
            "message": "Company research ingested and indexed into RAG vector store successfully.",
            "source_id": source.id,
            "document_id": doc.id if doc else None,
            "content_hash": result.get("content_hash"),
            "is_cached": result.get("is_cached", False),
            "status": result.get("status"),
            "chunks_count": result.get("chunks_count", 0)
        }

    except (InvalidURLError, SSRFProtectionError, DisallowedDomainError, UnsupportedContentTypeError, OversizedContentError, EmptyContentError) as client_err:
        logger.warning(f"Research validation/security rejection: {client_err}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(client_err))

    except FetchTimeoutError as timeout_err:
        logger.warning(f"Research fetch timeout: {timeout_err}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Target URL request timed out.")

    except HTTPFetchError as http_err:
        logger.warning(f"Upstream HTTP error: {http_err}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(http_err))

    except StaleRefreshFailedError as stale_err:
        logger.warning(f"Stale refresh failed: {stale_err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to refresh remote source: {stale_err.original_error}. Previous valid cached content preserved."
        )

    except Exception as exc:
        logger.error(f"Internal error during research processing: {exc}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal research processing error.")
