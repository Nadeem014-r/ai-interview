from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user_payload
from app.db.models import User, CandidateProfile
from app.schemas.auth import UserRegister, UserLogin, Token, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    normalized_email = user_in.email.strip().lower()
    
    # Check if user already exists (case-insensitive)
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    res = await db.execute(stmt)
    if res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered."
        )

    # Validate password length explicitly as safeguard
    if len(user_in.password.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )

    try:
        hashed_pw = get_password_hash(user_in.password)
        # Public candidate registration strictly enforces role="candidate"
        new_user = User(
            email=normalized_email,
            hashed_password=hashed_pw,
            full_name=user_in.full_name.strip(),
            role="candidate",
            is_active=True
        )
        db.add(new_user)
        await db.flush()

        # Atomically initialize CandidateProfile
        profile = CandidateProfile(
            user_id=new_user.id,
            target_role="Software Engineer",
            experience_level="entry"
        )
        db.add(profile)
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user account."
        )

    token_str = create_access_token(subject=new_user.id, role=new_user.role)
    return Token(
        access_token=token_str,
        token_type="bearer",
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role
    )

@router.post("/login", response_model=Token)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    normalized_email = user_in.email.strip().lower()
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive. Please contact support."
        )

    token_str = create_access_token(subject=user.id, role=user.role)
    return Token(
        access_token=token_str,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role
    )

@router.get("/me", response_model=UserOut)
async def get_current_user(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload.get("user_id")
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user
