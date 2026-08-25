import pytest
from app.interview.state_machine import AdaptiveStateMachine
from app.evaluation.scorer import DeterministicScorer

def test_adaptive_difficulty_progression():
    # Strong score (9.0) should increase difficulty easy -> medium -> hard
    diff, topic, scores, weak, strong = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="easy",
        last_eval_score=9.0,
        current_topic="Databases",
        covered_topics=[],
        remaining_topics=["Databases", "Concurrency"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert diff == "medium"
    assert "Databases" in strong

    # Weak score (3.0) should decrease difficulty hard -> medium
    diff2, topic2, scores2, weak2, strong2 = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="hard",
        last_eval_score=3.0,
        current_topic="Concurrency",
        covered_topics=[],
        remaining_topics=["Concurrency"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert diff2 == "medium"
    assert "Concurrency" in weak2

def test_deterministic_scoring():
    # Test weighted question score
    weighted = DeterministicScorer.calculate_question_weighted_score(
        correctness=10.0,
        relevance=10.0,
        reasoning=10.0,
        depth=10.0,
        communication=10.0
    )
    assert weighted == 10.0

    # Test overall interview score
    overall = DeterministicScorer.calculate_overall_interview_score([8.0, 9.0, 7.0])
    assert overall == 80.0
