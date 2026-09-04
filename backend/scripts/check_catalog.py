import asyncio
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.db.models import Company, Role


async def main():
    async with AsyncSessionLocal() as db:

        company_count = (
            await db.execute(
                select(func.count()).select_from(Company)
            )
        ).scalar()

        role_count = (
            await db.execute(
                select(func.count()).select_from(Role)
            )
        ).scalar()

        print("COMPANIES:", company_count)
        print("ROLES:", role_count)

        result = await db.execute(
            select(Company.id, Company.name)
            .order_by(Company.id)
        )

        print("\nCOMPANY LIST:")
        for company_id, name in result.all():
            print(company_id, "-", name)


asyncio.run(main())