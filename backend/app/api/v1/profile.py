from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.db.models import CandidateProfile, User
from app.schemas.auth import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("", response_model=ProfileOut)
async def get_profile(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return ProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        full_name=user.full_name,
        email=user.email,
        headline=profile.headline,
        target_role=profile.target_role,
        experience_level=profile.experience_level or "entry",
        bio=profile.bio,
        phone=profile.phone,
        university=profile.university,
        degree=profile.degree,
        branch=profile.branch,
        graduation_year=profile.graduation_year,
        skills=profile.skills or [],
        experience=profile.experience or [],
        projects=profile.projects or [],
        certifications=profile.certifications or [],
        preferences=profile.preferences or {},
        github_url=profile.github_url,
        linkedin_url=profile.linkedin_url,
        created_at=profile.created_at
    )

@router.put("", response_model=ProfileOut)
async def update_profile(
    update_data: ProfileUpdate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)

    data_dict = update_data.model_dump(exclude_unset=True)
    if "full_name" in data_dict and data_dict["full_name"]:
        user.full_name = data_dict.pop("full_name")

    for field, val in data_dict.items():
        if hasattr(profile, field):
            setattr(profile, field, val)

    await db.commit()
    await db.refresh(profile)
    await db.refresh(user)

    return ProfileOut(
        id=profile.id,
        user_id=profile.user_id,
        full_name=user.full_name,
        email=user.email,
        headline=profile.headline,
        target_role=profile.target_role,
        experience_level=profile.experience_level or "entry",
        bio=profile.bio,
        phone=profile.phone,
        university=profile.university,
        degree=profile.degree,
        branch=profile.branch,
        graduation_year=profile.graduation_year,
        skills=profile.skills or [],
        experience=profile.experience or [],
        projects=profile.projects or [],
        certifications=profile.certifications or [],
        preferences=profile.preferences or {},
        github_url=profile.github_url,
        linkedin_url=profile.linkedin_url,
        created_at=profile.created_at
    )

