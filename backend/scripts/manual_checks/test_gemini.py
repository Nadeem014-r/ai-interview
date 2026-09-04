import asyncio

from app.ai.factory import AIFactory


async def main():
    provider = AIFactory.get_llm_provider()

    print("=" * 60)
    print("BEFORE")
    print(vars(provider))
    print("=" * 60)

    try:
        result = await provider.generate_json(
            """
            Return JSON with exactly one field:
            {"message": "hello"}
            """,
            system_prompt="You are a test assistant. Return only valid JSON."
        )

        print("=" * 60)
        print("RESULT")
        print(result)
        print("=" * 60)

    except Exception as e:
        print("=" * 60)
        print("ERROR")
        print(type(e).__name__)
        print(str(e))
        print("=" * 60)

    print("AFTER")
    print(vars(provider))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())