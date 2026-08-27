import asyncio
import asyncpg
from app.core.config import settings


async def main():
    database_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1
    )

    conn = await asyncpg.connect(database_url)

    await conn.execute("""
        ALTER TABLE interview_states
        ADD COLUMN IF NOT EXISTS topic_question_counts JSON DEFAULT '{}'::json
    """)

    print("DONE: topic_question_counts added")

    await conn.close()


asyncio.run(main())