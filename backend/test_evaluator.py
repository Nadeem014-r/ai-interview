import asyncio
from app.evaluation.evaluator import AnswerEvaluator


async def test():
    question = "Explain how indexing improves query performance in relational databases."

    concepts = [
        "B-Tree structure",
        "Reduced disk I/O",
        "Search complexity O(log N)",
        "Write overhead trade-offs",
    ]

    answers = [
        ("UNKNOWN", "I don't know."),
        (
            "IRRELEVANT",
            "Paris is the capital of France and the weather is nice.",
        ),
        (
            "PARTIAL",
            "I think indexing makes queries faster.",
        ),
        (
            "STRONG",
            "Database indexes commonly use B+ trees to organize data. "
            "They reduce the amount of data that must be scanned and can "
            "provide logarithmic lookup behavior. The trade-off is extra "
            "storage and additional work during inserts, updates, and deletes.",
        ),
    ]

    for name, answer in answers:
        result = await AnswerEvaluator.evaluate_answer(
            question_text=question,
            expected_concepts=concepts,
            candidate_answer=answer,
            topic="Database Indexing",
            question_type="technical",
        )

        print("=" * 60)
        print(name)
        print("ANSWER:", answer)
        print("SCORE:", result.get("overall_question_score"))
        print("QUALITY:", result.get("answer_quality"))
        print("ACTION:", result.get("recommended_action"))
        print("FEEDBACK:", result.get("feedback_text"))
        print("EVIDENCE:", result.get("evidence"))


asyncio.run(test())