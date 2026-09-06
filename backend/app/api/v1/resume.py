import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.core.config import settings
from app.db.models import Resume, ResumeProfile, CandidateProfile
from app.schemas.resume import ResumeOut, ResumeProfileUpdate
from app.resume.validator import ResumeValidator
from app.resume.parser import ResumeParser

router = APIRouter(prefix="/resume", tags=["Resume Intelligence"])

# Read granularity for bounded upload reads -- not a size limit. The limit
# itself stays settings.MAX_FILE_SIZE_MB, enforced by ResumeValidator.
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024

@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]

    # Validate filename, extension and MIME type before reading any bytes.
    ext = ResumeValidator.validate_file_metadata(file)

    # Read the body in bounded chunks and stop as soon as the configured limit
    # is exceeded, so an oversized upload is never fully buffered in memory.
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        chunks = []
        total_read = 0
        while True:
            chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total_read += len(chunk)
            if total_read > max_bytes:
                # Already past the limit; the size check below rejects it.
                break
        file_bytes = b"".join(chunks)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file."
        )

    # Validate size, non-emptiness, and header signature
    ResumeValidator.validate_file_content(file_bytes, ext)

    # Generate a safe, unique filename in a user-scoped storage directory
    safe_id = uuid.uuid4().hex
    safe_filename = f"{safe_id}{ext}"
    user_upload_dir = os.path.join(settings.UPLOAD_DIR, f"user_{user_id}")
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, safe_filename)

    file_written = False
    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        file_written = True

        # Extract text & parse resume intelligence
        raw_text = ResumeParser.extract_text_from_bytes(file_bytes, file.filename or f"resume{ext}")
        parsed_json = await ResumeParser.parse_resume_content(raw_text)

        # Sanitize display filename for database record (strip any directory components)
        display_name = os.path.basename(file.filename or f"resume{ext}")

        new_resume = Resume(
            user_id=user_id,
            filename=display_name,
            file_path=file_path,
            file_size=len(file_bytes),
            mime_type=file.content_type or "application/octet-stream"
        )
        db.add(new_resume)
        await db.flush()

        new_profile = ResumeProfile(
            resume_id=new_resume.id,
            raw_text=raw_text,
            explicit_facts=parsed_json.get("explicit_facts", {}),
            model_inferred=parsed_json.get("model_inferred", {}),
            skills=parsed_json.get("skills", []),
            projects=parsed_json.get("projects", []),
            education=parsed_json.get("education", []),
            experience=parsed_json.get("experience", []),
            technologies=parsed_json.get("technologies", [])
        )
        db.add(new_profile)

        # Synchronize with CandidateProfile on upload or replace
        stmt_prof = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        res_prof = await db.execute(stmt_prof)
        cand_prof = res_prof.scalars().first()

        if cand_prof:
            if new_profile.skills:
                cand_prof.skills = list(new_profile.skills)
            if new_profile.projects:
                cand_prof.projects = list(new_profile.projects)
            if new_profile.education and len(new_profile.education) > 0:
                first_edu = new_profile.education[0]
                if first_edu.get("institution"):
                    cand_prof.university = first_edu.get("institution")
                if first_edu.get("degree"):
                    cand_prof.degree = first_edu.get("degree")
            if new_profile.explicit_facts.get("phone"):
                cand_prof.phone = new_profile.explicit_facts.get("phone")
        else:
            cand_prof = CandidateProfile(
                user_id=user_id,
                skills=list(new_profile.skills) if new_profile.skills else [],
                projects=list(new_profile.projects) if new_profile.projects else [],
                university=new_profile.education[0].get("institution") if new_profile.education and len(new_profile.education) > 0 else None,
                degree=new_profile.education[0].get("degree") if new_profile.education and len(new_profile.education) > 0 else None,
                phone=new_profile.explicit_facts.get("phone")
            )
            db.add(cand_prof)

        await db.commit()
        await db.refresh(new_resume)

        # ── Pass 2: Taxonomy Enrichment (additive, non-blocking) ──────────────
        # Runs after commit so a taxonomy failure never blocks the upload flow.
        try:
            import logging as _logging
            from app.resume.taxonomy_parser import TaxonomyParser
            _tax_logger = _logging.getLogger("ai_interviewer.resume_api")
            taxonomy_result = await TaxonomyParser.enrich_profile(
                parsed_profile=parsed_json,
                raw_text_snippet=raw_text[:1000],
            )
            # Store taxonomy inside model_inferred.taxonomy (JSON column, backward-compatible)
            existing_inferred = new_profile.model_inferred or {}
            existing_inferred["taxonomy"] = taxonomy_result.taxonomy.model_dump()
            existing_inferred["evaluation_skills"] = taxonomy_result.evaluation_skills
            existing_inferred["noise_filtered"] = taxonomy_result.noise_filtered
            new_profile.model_inferred = existing_inferred
            await db.commit()
            _tax_logger.info(
                f"Taxonomy enrichment complete for resume {new_resume.id}: "
                f"{len(taxonomy_result.evaluation_skills)} evaluation skills, "
                f"{len(taxonomy_result.noise_filtered)} noise items filtered."
            )
        except Exception as _tax_exc:
            import logging as _logging
            _logging.getLogger("ai_interviewer.resume_api").warning(
                f"Taxonomy enrichment failed (non-fatal, upload still succeeded): {_tax_exc}"
            )

        # Re-fetch full resume with resume_profile relationship loaded
        stmt = select(Resume).options(selectinload(Resume.resume_profile)).where(Resume.id == new_resume.id)
        res = await db.execute(stmt)
        return res.scalars().first()


    except HTTPException:
        await db.rollback()
        if file_written and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise
    except Exception as e:
        await db.rollback()
        if file_written and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the resume: {str(e)}"
        )

@router.get("", response_model=list[ResumeOut])
async def get_my_resumes(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/current", response_model=ResumeOut)
async def get_current_resume(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    )
    res = await db.execute(stmt)
    resume = res.scalars().first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active resume found for this candidate."
        )
    return resume

@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume_by_id(
    resume_id: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    res = await db.execute(stmt)
    resume = res.scalars().first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found or unauthorized access."
        )
    return resume

@router.put("/{resume_id}/profile", response_model=ResumeOut)
async def update_parsed_resume_profile(
    resume_id: int,
    update_in: ResumeProfileUpdate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    res = await db.execute(stmt)
    resume = res.scalars().first()
    if not resume or not resume.resume_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume or parsed profile not found or unauthorized access."
        )

    prof = resume.resume_profile
    data = update_in.model_dump(exclude_unset=True)
    for field, val in data.items():
        if val is not None and hasattr(prof, field):
            setattr(prof, field, val)

    await db.commit()
    
    # Reload updated resume with profile
    stmt = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.id == resume_id)
    )
    res = await db.execute(stmt)
    return res.scalars().first()
