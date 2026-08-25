from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import require_role
from app.db.models import User, Interview, Company, Role, Question, Report

router = APIRouter(prefix="/admin", tags=["Admin & Placement Cell Dashboard"])

@router.get("/stats")
async def get_system_stats(
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    users_count = (await db.execute(select(func.count(User.id)))).scalar()
    interviews_count = (await db.execute(select(func.count(Interview.id)))).scalar()
    companies_count = (await db.execute(select(func.count(Company.id)))).scalar()
    reports_count = (await db.execute(select(func.count(Report.id)))).scalar()
    
    avg_score = (await db.execute(select(func.avg(Report.overall_score)))).scalar() or 0.0

    return {
        "total_candidates": users_count,
        "total_interviews": interviews_count,
        "total_companies": companies_count,
        "total_reports": reports_count,
        "average_platform_score": round(avg_score, 1)
    }

@router.get("/candidates")
async def list_candidates(
    payload: dict = Depends(require_role(["admin", "placement_staff"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.role == "candidate")
    res = await db.execute(stmt)
    users = res.scalars().all()
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "created_at": u.created_at} for u in users]
