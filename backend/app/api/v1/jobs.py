from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.db.models import Company, Role, Resume, ResumeProfile, CandidateProfile
from app.matching.matcher import JobMatchingEngine

router = APIRouter(prefix="/jobs", tags=["Job Matching & Recommendations"])

class MatchBreakdown(BaseModel):
    skills_score: float
    experience_score: float
    education_score: float
    projects_score: float

class JobMatchResult(BaseModel):
    role_id: int
    role_title: str
    company_id: int
    company_name: str
    role_level: str
    overall_score: float
    breakdown: MatchBreakdown
    matched_skills: List[str]
    missing_skills: List[str]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]

@router.get("/matches", response_model=List[JobMatchResult])
async def get_all_job_matches(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]

    # 1. Fetch candidate's latest resume or profile
    stmt_resume = select(Resume).options(selectinload(Resume.resume_profile)).where(
        Resume.user_id == user_id
    ).order_by(Resume.created_at.desc())
    res_resume = await db.execute(stmt_resume)
    latest_resume = res_resume.scalars().first()

    stmt_profile = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res_profile = await db.execute(stmt_profile)
    cand_profile = res_profile.scalars().first()

    candidate_skills = []
    candidate_exp_level = "entry"
    candidate_education = []
    candidate_projects = []

    if latest_resume and latest_resume.resume_profile:
        rp = latest_resume.resume_profile
        candidate_skills = rp.skills or []
        candidate_education = rp.education or []
        candidate_projects = rp.projects or []
        candidate_exp_level = rp.model_inferred.get("estimated_experience_level", "entry") if rp.model_inferred else "entry"

    if cand_profile:
        if not candidate_skills and cand_profile.skills:
            candidate_skills = cand_profile.skills
        if cand_profile.experience_level:
            candidate_exp_level = cand_profile.experience_level
        if not candidate_education and cand_profile.university:
            candidate_education = [{"degree": cand_profile.degree or "B.Tech", "institution": cand_profile.university}]
        if not candidate_projects and cand_profile.projects:
            candidate_projects = cand_profile.projects

    # If the candidate has no active resume and no profile skills, return []
    has_active_resume = bool(
        latest_resume
        and latest_resume.resume_profile
        and (
            latest_resume.resume_profile.skills
            or latest_resume.resume_profile.raw_text
        )
    )
    has_profile_skills = bool(cand_profile and cand_profile.skills)

    if not has_active_resume and not has_profile_skills:
        return []

    # 2. Fetch all roles across all companies
    stmt_roles = select(Role).options(selectinload(Role.company))
    res_roles = await db.execute(stmt_roles)
    roles = res_roles.scalars().all()

    results = []
    for role in roles:
        match_data = JobMatchingEngine.match_candidate_to_role(
            candidate_skills=candidate_skills,
            candidate_experience_level=candidate_exp_level,
            candidate_education=candidate_education,
            candidate_projects=candidate_projects,
            role=role,
            company=role.company
        )
        results.append(match_data)

    # Sort descending by overall compatibility score
    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return results

@router.get("/matches/{role_id}", response_model=JobMatchResult)
async def get_single_role_match(
    role_id: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]

    stmt_role = select(Role).options(selectinload(Role.company)).where(Role.id == role_id)
    res_role = await db.execute(stmt_role)
    role = res_role.scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Target job role not found.")

    stmt_resume = select(Resume).options(selectinload(Resume.resume_profile)).where(
        Resume.user_id == user_id
    ).order_by(Resume.created_at.desc())
    res_resume = await db.execute(stmt_resume)
    latest_resume = res_resume.scalars().first()

    stmt_profile = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res_profile = await db.execute(stmt_profile)
    cand_profile = res_profile.scalars().first()

    candidate_skills = []
    candidate_exp_level = "entry"
    candidate_education = []
    candidate_projects = []

    if latest_resume and latest_resume.resume_profile:
        rp = latest_resume.resume_profile
        candidate_skills = rp.skills or []
        candidate_education = rp.education or []
        candidate_projects = rp.projects or []
        candidate_exp_level = rp.model_inferred.get("estimated_experience_level", "entry") if rp.model_inferred else "entry"

    if cand_profile:
        if not candidate_skills and cand_profile.skills:
            candidate_skills = cand_profile.skills
        if cand_profile.experience_level:
            candidate_exp_level = cand_profile.experience_level
        if not candidate_education and cand_profile.university:
            candidate_education = [{"degree": cand_profile.degree or "B.Tech", "institution": cand_profile.university}]

    match_data = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level=candidate_exp_level,
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        role=role,
        company=role.company
    )
    return match_data
