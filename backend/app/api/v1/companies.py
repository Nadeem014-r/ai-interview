from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user_payload
from app.db.models import Company, Role
from app.schemas.interview import CompanyOut, RoleOut

router = APIRouter(prefix="/companies", tags=["Companies & Roles"])

@router.get("", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    stmt = select(Company)
    res = await db.execute(stmt)
    companies = res.scalars().all()
    
    # Pre-populate dummy company catalog if database is empty
    if not companies:
        c1 = Company(
            name="Google",
            slug="google",
            description="Leading global technology company focused on search, cloud, AI, and systems engineering.",
            website="https://careers.google.com",
            target_roles=["Software Engineer", "Systems Architect", "ML Engineer"],
            culture_keywords=["Scalability", "Clean Code", "System Design", "Algorithmic Efficiency"]
        )
        c2 = Company(
            name="Amazon",
            slug="amazon",
            description="Global e-commerce and cloud computing giant specializing in distributed systems and cloud services.",
            website="https://amazon.jobs",
            target_roles=["SDE I", "SDE II", "DevOps Engineer"],
            culture_keywords=["Customer Obsession", "Ownership", "Bias for Action", "High Standards"]
        )
        c3 = Company(
            name="Microsoft",
            slug="microsoft",
            description="Pioneer in operating systems, Azure cloud, productivity tools, and enterprise software.",
            website="https://careers.microsoft.com",
            target_roles=["Software Engineer", "Cloud Solutions Architect"],
            culture_keywords=["Growth Mindset", "Diversity", "Innovation", "Enterprise Reliability"]
        )
        db.add_all([c1, c2, c3])
        await db.commit()
        
        r1 = Role(company_id=c1.id, title="Software Engineer (Backend)", level="Entry / L3", description="Build scalable distributed backend microservices.", required_skills=["Python", "FastAPI", "Data Structures", "System Design"], key_topics=["Data Structures", "Relational Databases", "Distributed Systems"], interview_categories=["Technical", "Behavioral"])
        r2 = Role(company_id=c2.id, title="Software Development Engineer (SDE-1)", level="L4 / Entry", description="Design high-performance e-commerce and cloud microservices.", required_skills=["Java", "Python", "SQL", "OOP"], key_topics=["Object-Oriented Design", "Concurrency", "Database Indexing"], interview_categories=["Coding", "Leadership Principles"])
        r3 = Role(company_id=c3.id, title="Cloud Backend Engineer", level="L59 / Graduate", description="Implement enterprise cloud microservices on Azure.", required_skills=["C#", "Python", "Docker", "REST APIs"], key_topics=["Cloud Microservices", "API Security", "Database Tuning"], interview_categories=["Technical", "System Architecture"])
        db.add_all([r1, r2, r3])
        await db.commit()

        stmt = select(Company)
        res = await db.execute(stmt)
        companies = res.scalars().all()

    return companies

@router.get("/{company_id}/roles", response_model=list[RoleOut])
async def list_company_roles(company_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Role).where(Role.company_id == company_id)
    res = await db.execute(stmt)
    return res.scalars().all()
