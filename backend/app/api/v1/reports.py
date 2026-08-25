from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.db.models import Report, Interview
from app.schemas.interview import ReportOut
from app.reports.generator import ReportGenerator

router = APIRouter(prefix="/reports", tags=["Candidate Reports"])

@router.get("/{interview_id}", response_model=ReportOut)
async def get_report(
    interview_id: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    user_role = payload.get("role", "candidate")

    stmt_int = select(Interview).where(Interview.id == interview_id)
    res_int = await db.execute(stmt_int)
    interview = res_int.scalars().first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if interview.candidate_id != user_id and user_role not in ["admin", "placement_staff"]:
        raise HTTPException(status_code=403, detail="Unauthorized to view this interview report.")

    stmt = select(Report).where(Report.interview_id == interview_id)
    res = await db.execute(stmt)
    report = res.scalars().first()
    
    if not report:
        report_gen = ReportGenerator(db)
        report = await report_gen.generate_interview_report(interview_id)

    return report

