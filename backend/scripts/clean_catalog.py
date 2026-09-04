import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


KEEP_SLUGS = [
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


async def clean_database():
    async with AsyncSessionLocal() as db:

        print("Cleaning unwanted companies and related data...")

        # Delete document chunks belonging to documents
        # whose sources belong to unwanted companies.
        await db.execute(text("""
            DELETE FROM document_chunks
            WHERE document_id IN (
                SELECT d.id
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                WHERE s.company_id IN (
                    SELECT id FROM companies
                    WHERE slug NOT IN :keep_slugs
                )
            )
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        # Delete documents
        await db.execute(text("""
            DELETE FROM documents
            WHERE source_id IN (
                SELECT id
                FROM sources
                WHERE company_id IN (
                    SELECT id FROM companies
                    WHERE slug NOT IN :keep_slugs
                )
            )
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        # Delete sources
        await db.execute(text("""
            DELETE FROM sources
            WHERE company_id IN (
                SELECT id FROM companies
                WHERE slug NOT IN :keep_slugs
            )
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        # Delete questions belonging to unwanted companies
        # or roles belonging to unwanted companies.
        await db.execute(text("""
            DELETE FROM questions
            WHERE company_id IN (
                SELECT id FROM companies
                WHERE slug NOT IN :keep_slugs
            )
            OR role_id IN (
                SELECT r.id
                FROM roles r
                JOIN companies c ON c.id = r.company_id
                WHERE c.slug NOT IN :keep_slugs
            )
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        # Delete roles belonging to unwanted companies.
        await db.execute(text("""
            DELETE FROM roles
            WHERE company_id IN (
                SELECT id FROM companies
                WHERE slug NOT IN :keep_slugs
            )
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        # Finally delete unwanted companies.
        await db.execute(text("""
            DELETE FROM companies
            WHERE slug NOT IN :keep_slugs
        """), {"keep_slugs": tuple(KEEP_SLUGS)})

        await db.commit()

        result = await db.execute(text("""
            SELECT id, name, slug
            FROM companies
            ORDER BY id
        """))

        companies = result.fetchall()

        print()
        print("================================")
        print("DATABASE CLEANUP COMPLETE")
        print("================================")
        print(f"Remaining companies: {len(companies)}")
        print()

        for company in companies:
            print(f"{company.id} - {company.name} ({company.slug})")


async def main():
    print("Starting database cleanup...")
    await clean_database()


if __name__ == "__main__":
    asyncio.run(main())