import asyncio

from app.ai.factory import AIFactory


async def main():
    provider = AIFactory.get_llm_provider()

    print("=" * 60)
    print("BEFORE")
    print(vars(provider))

    prompt = """
Generate one realistic software engineering interview question
about Data Structures.

The question should sound like a human interviewer speaking naturally.

Return JSON only:

{
    "question_text": "...",
    "expected_concepts": ["...", "..."],
    "follow_ups": ["..."]
}
"""

    result = await provider.generate_json(
        prompt,
        system_prompt=(
            "You are a senior software engineering interviewer. "
            "Ask natural, conversational questions."
        ),
    )

    print("=" * 60)
    print("RESULT")
    print(result)

    print("=" * 60)
    print("AFTER")
    print(vars(provider))


if __name__ == "__main__":
    asyncio.run(main())