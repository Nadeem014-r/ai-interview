from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.database import get_db
from app.core.security import require_role
from app.core.audit import AuditLogger
from app.db.models import User, Interview, Company, Role, Question, Report

router = APIRouter(prefix="/admin", tags=["Admin & Placement Cell Dashboard"])

@router.get("/stats")
async def get_system_stats(
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    users_count = (await db.execute(select(func.count(User.id)).where(User.role == "candidate"))).scalar() or 0
    interviews_count = (await db.execute(select(func.count(Interview.id)))).scalar() or 0
    companies_count = (await db.execute(select(func.count(Company.id)))).scalar() or 0
    reports_count = (await db.execute(select(func.count(Report.id)))).scalar() or 0
    
    avg_score = (await db.execute(select(func.avg(Report.overall_score)))).scalar() or 0.0

    AuditLogger.log_event(
        event_type="ADMIN_VIEW_STATS",
        user_id=payload.get("user_id"),
        user_role=payload.get("role"),
        resource="system_stats"
    )

    return {
        "total_candidates": users_count,
        "total_interviews": interviews_count,
        "total_companies": companies_count,
        "total_reports": reports_count,
        "average_platform_score": round(float(avg_score), 1)
    }

@router.get("/candidates")
async def list_candidates(
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.role == "candidate").order_by(User.created_at.desc())
    res = await db.execute(stmt)
    users = res.scalars().all()

    AuditLogger.log_event(
        event_type="ADMIN_LIST_CANDIDATES",
        user_id=payload.get("user_id"),
        user_role=payload.get("role"),
        resource="candidates_list"
    )

    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "created_at": u.created_at} for u in users]

@router.get("/interviews")
async def list_admin_interviews(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Interview)
        .options(
            selectinload(Interview.company),
            selectinload(Interview.role),
            selectinload(Interview.candidate)
        )
        .order_by(Interview.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(Interview.status == status_filter)

    res = await db.execute(stmt)
    interviews = res.scalars().all()

    AuditLogger.log_event(
        event_type="ADMIN_LIST_INTERVIEWS",
        user_id=payload.get("user_id"),
        user_role=payload.get("role"),
        resource="interviews_list",
        details={"status_filter": status_filter, "count": len(interviews)}
    )

    return [
        {
            "id": i.id,
            "candidate_name": i.candidate.full_name if getattr(i, "candidate", None) else "Candidate",
            "candidate_email": i.candidate.email if getattr(i, "candidate", None) else None,
            "company_name": i.company.name if getattr(i, "company", None) else "Company",
            "role_title": i.role.title if getattr(i, "role", None) else "Role",
            "status": i.status,
            "mode": i.mode,
            "duration_minutes": i.duration_minutes,
            "created_at": i.created_at
        }
        for i in interviews
    ]
