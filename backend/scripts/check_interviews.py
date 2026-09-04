import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:

        result = await db.execute(text("""
            SELECT
                c.id,
                c.name,
                c.slug,
                COUNT(i.id) AS interview_count
            FROM companies c
            JOIN interviews i ON i.company_id = c.id
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
            GROUP BY c.id, c.name, c.slug
            ORDER BY c.id
        """))

        rows = result.fetchall()

        print("\nUnwanted companies referenced by interviews:")
        print("--------------------------------------------")

        for row in rows:
            print(
                f"{row.id} - {row.name} - "
                f"{row.slug} - interviews: {row.interview_count}"
            )

        print("--------------------------------------------")
        print(f"Companies involved: {len(rows)}")
        print(
            f"Total interviews: "
            f"{sum(row.interview_count for row in rows)}"
        )


if __name__ == "__main__":
    asyncio.run(main())