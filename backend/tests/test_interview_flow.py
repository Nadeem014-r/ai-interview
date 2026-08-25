import pytest
from app.evaluation.evaluator import AnswerEvaluator
from app.evaluation.scorer import DeterministicScorer

@pytest.mark.asyncio
async def test_answer_evaluator_scoring():
    eval_result = await AnswerEvaluator.evaluate_answer(
        question_text="Explain how B-Tree indexing works in relational databases.",
        expected_concepts=["B-Tree node structure", "Disk I/O reduction", "O(log N) search"],
        candidate_answer="B-Tree indexing uses balanced tree node structures to reduce disk I/O operations and achieves O(log N) search complexity for fast lookups.",
        topic="Relational Databases"
    )

    assert eval_result["overall_question_score"] >= 6.0
    assert eval_result["correctness_score"] >= 5.0
    assert "feedback_text" in eval_result
    assert "confidence_score" in eval_result

def test_deterministic_scoring_weights():
    # 30% correctness, 20% relevance, 20% reasoning, 15% depth, 15% communication
    score = DeterministicScorer.calculate_question_weighted_score(
        correctness=10.0,
        relevance=10.0,
        reasoning=10.0,
        depth=10.0,
        communication=10.0
    )
    assert score == 10.0

    score_mixed = DeterministicScorer.calculate_question_weighted_score(
        correctness=8.0,
        relevance=8.0,
        reasoning=8.0,
        depth=8.0,
        communication=8.0
    )
    assert score_mixed == 8.0
