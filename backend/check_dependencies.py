import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:

        result = await db.execute(text("""
            SELECT COUNT(*)
            FROM companies
            WHERE slug NOT IN (
                'google',
                'amazon',
                'microsoft',
                'meta',
                'apple',
                'netflix',
                'adobe',
                'ibm',
                'oracle',
                'infosys'
            )
        """))

        unwanted = result.scalar()

        result = await db.execute(text("""
            SELECT COUNT(*)
            FROM interviews i
            JOIN companies c ON c.id = i.company_id
            WHERE c.slug NOT IN (
                'google',
                'amazon',
                'microsoft',
                'meta',
                'apple',
                'netflix',
                'adobe',
                'ibm',
                'oracle',
                'infosys'
            )
        """))

        interviews = result.scalar()

        print(f"Unwanted companies: {unwanted}")
        print(f"Interviews using unwanted companies: {interviews}")


if __name__ == "__main__":
    asyncio.run(main())