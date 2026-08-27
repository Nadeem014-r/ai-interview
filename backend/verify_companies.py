import asyncio

from sqlalchemy import text
from app.core.database import AsyncSessionLocal


APPROVED_SLUGS = [
    "google",
    "amazon",
    "microsoft",
    "meta",
    "apple",
    "netflix",
    "adobe",
    "ibm",
    "oracle",
    "infosys",
]


async def main():
    async with AsyncSessionLocal() as db:

        print("\n================================")
        print("DATABASE COMPANY VERIFICATION")
        print("================================")

        # 1. Count total companies
        result = await db.execute(
            text("SELECT COUNT(*) FROM companies")
        )
        total = result.scalar()

        print(f"\nTotal companies: {total}")

        # 2. Show all remaining companies
        result = await db.execute(
            text("""
                SELECT id, name, slug
                FROM companies
                ORDER BY slug
            """)
        )

        companies = result.fetchall()

        print("\nRemaining companies:")
        print("--------------------------------")

        for company in companies:
            print(
                f"ID: {company.id} | "
                f"Name: {company.name} | "
                f"Slug: {company.slug}"
            )

        # 3. Check unwanted companies
        result = await db.execute(
            text("""
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
            """)
        )

        unwanted = result.scalar()

        print("\nUnwanted companies:", unwanted)

        # 4. Check whether any approved company is missing
        result = await db.execute(
            text("""
                SELECT slug
                FROM companies
                WHERE slug IN (
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
                ORDER BY slug
            """)
        )

        existing_slugs = {row.slug for row in result.fetchall()}
        approved_slugs = set(APPROVED_SLUGS)

        missing = approved_slugs - existing_slugs

        print("\nMissing approved companies:", len(missing))

        if missing:
            for slug in sorted(missing):
                print("MISSING:", slug)

        # 5. Final verification
        print("\n================================")
        print("FINAL RESULT")
        print("================================")

        if (
            total == 10
            and unwanted == 0
            and len(missing) == 0
            and existing_slugs == approved_slugs
        ):
            print("SUCCESS!")
            print("Database contains exactly the 10 approved companies.")
        else:
            print("ERROR!")
            print("Database is NOT in the expected state.")

        await db.rollback()


if __name__ == "__main__":
    asyncio.run(main())