from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.db.models import Company, Role
from app.schemas.interview import CompanyOut, RoleOut

router = APIRouter(prefix="/companies", tags=["Companies & Roles"])

@router.get("", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    stmt = select(Company).options(selectinload(Company.roles))
    res = await db.execute(stmt)
    companies = res.scalars().all()
    
    # Seed official company & role catalog if database is empty
    if not companies:
        from app.db.seed_data import seed_all_companies_and_roles
        await seed_all_companies_and_roles(db)
        stmt = select(Company).options(selectinload(Company.roles))
        res = await db.execute(stmt)
        companies = res.scalars().all()

    return companies

@router.get("/{company_id}/roles", response_model=list[RoleOut])
async def list_company_roles(company_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Role).where(Role.company_id == company_id)
    res = await db.execute(stmt)
    return res.scalars().all()
