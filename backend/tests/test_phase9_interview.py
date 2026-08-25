"""Phase 9: Comprehensive Interview Intelligence Layer Test Suite.

Tests interview planning, adaptive state machine, gradual difficulty adaptation,
topic selection, skill scoring, confidence evolution, conversational follow-up decisions,
duplicate prevention, time boundaries, stop conditions, and fallback mechanisms.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from app.interview.planner import InterviewPlanner
from app.interview.scoring import ScoringManager
from app.interview.conversation import FollowUpEngine
from app.interview.timer import InterviewTimer
from app.interview.state_machine import AdaptiveStateMachine
from app.interview.question_selector import (
    QuestionSelector,
    normalize_text_for_comparison,
    is_duplicate_question,
    validate_question_data
)
from app.interview.engine import AdaptiveInterviewEngine
from app.db.models import Interview, InterviewState, Question, Role


# ==============================================================================
# A. Interview Planning Tests
# ==============================================================================

def test_planner_role_and_skills_prioritization():
    """Verify planner combines and prioritizes role topics and required skills."""
    plan = InterviewPlanner.plan_interview(
        role_title="Backend Engineer",
        key_topics=["Distributed Caching", "Database Indexing"],
        required_skills=["Python", "FastAPI", "PostgreSQL"],
        candidate_level="mid",
        interview_type="technical",
        duration_minutes=30
    )
    assert plan["target_question_count"] == 5
    assert "Distributed Caching" in plan["primary_topics"]
    assert "Database Indexing" in plan["primary_topics"]
    assert "FastAPI" in plan["primary_topics"] or "FastAPI" in plan["secondary_topics"]
    assert plan["target_level"] == "mid"


def test_planner_duration_aware_stages():
    """Verify planner adapts stages and question limits for 15m vs 60m interviews."""
    plan_15 = InterviewPlanner.plan_interview("Dev", ["DSA"], ["Python"], duration_minutes=15)
    assert plan_15["target_question_count"] == 3
    assert "wrapup" in plan_15["stages"]

    plan_60 = InterviewPlanner.plan_interview("Dev", ["DSA", "System Design", "OS", "DB"], ["Go"], duration_minutes=60)
    assert plan_60["target_question_count"] == 8
    assert "deep_dive" in plan_60["stages"]
    assert "resume_discussion" in plan_60["stages"]


def test_planner_interview_type_adaptation():
    """Verify planner tailors fallback topics and stages for HR and Behavioral types."""
    plan_hr = InterviewPlanner.plan_interview("Candidate", [], [], interview_type="hr", duration_minutes=30)
    assert "Introduction & Motivation" in plan_hr["primary_topics"]
    assert plan_hr["interview_type"] == "hr"

    plan_behav = InterviewPlanner.plan_interview("Lead", [], [], interview_type="behavioral", duration_minutes=30)
    assert any("Ownership" in t or "Teamwork" in t for t in plan_behav["primary_topics"])


# ==============================================================================
# B. State Machine Progression & Transition Safety Tests
# ==============================================================================

def test_state_machine_deterministic_stages():
    """Verify state machine progresses stages realistically from intro to wrapup."""
    # 0 questions -> intro
    assert AdaptiveStateMachine.determine_next_stage(0, 1800, 1800) == "intro"
    # 1 question -> warmup
    assert AdaptiveStateMachine.determine_next_stage(1, 1500, 1800) == "warmup"
    # 2 questions -> core
    assert AdaptiveStateMachine.determine_next_stage(2, 1200, 1800) == "core"
    # 4 questions -> deep_dive
    assert AdaptiveStateMachine.determine_next_stage(4, 900, 1800, "technical") == "deep_dive"
    # 6 questions -> resume_discussion
    assert AdaptiveStateMachine.determine_next_stage(6, 600, 1800) == "resume_discussion"
    # Low time (<= 120s) -> wrapup
    assert AdaptiveStateMachine.determine_next_stage(3, 100, 1800) == "wrapup"


def test_state_machine_invalid_transition_protection():
    """Verify state machine blocks invalid transitions like wrapup back to active stages."""
    assert AdaptiveStateMachine.validate_transition("intro", "core") is True
    assert AdaptiveStateMachine.validate_transition("core", "deep_dive") is True
    assert AdaptiveStateMachine.validate_transition("wrapup", "wrapup") is True
    assert AdaptiveStateMachine.validate_transition("wrapup", "core") is False
    assert AdaptiveStateMachine.validate_transition("wrapup", "intro") is False


# ==============================================================================
# C. Difficulty Adaptation Tests (Gradual, Bounded, Non-Oscillating)
# ==============================================================================

def test_difficulty_adaptation_gradual_increase_and_bounding():
    """Verify score >= 8.0 increases difficulty one step at a time and bounds at hard."""
    diff, topic, scores, weak, strong = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="easy",
        last_eval_score=8.5,
        current_topic="Python",
        covered_topics=[],
        remaining_topics=["Databases"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert diff == "medium"
    assert "Python" in strong

    # Next strong answer on medium -> moves to hard
    diff2, _, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="medium",
        last_eval_score=9.0,
        current_topic="Databases",
        covered_topics=["Python"],
        remaining_topics=[],
        skill_scores=scores,
        weak_topics=weak,
        strong_topics=strong
    )
    assert diff2 == "hard"

    # Next strong answer on hard -> remains hard (bounded)
    diff3, _, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="hard",
        last_eval_score=9.5,
        current_topic="Databases",
        covered_topics=["Python"],
        remaining_topics=[],
        skill_scores=scores,
        weak_topics=weak,
        strong_topics=strong
    )
    assert diff3 == "hard"


def test_difficulty_adaptation_gradual_decrease_and_bounding():
    """Verify score < 5.0 decreases difficulty one step at a time and bounds at easy."""
    diff, topic, scores, weak, strong = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="hard",
        last_eval_score=4.0,
        current_topic="Distributed Systems",
        covered_topics=[],
        remaining_topics=["Databases"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert diff == "medium"
    assert "Distributed Systems" in weak

    # Another struggle on medium -> moves to easy
    diff2, _, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="medium",
        last_eval_score=3.5,
        current_topic="Databases",
        covered_topics=["Distributed Systems"],
        remaining_topics=[],
        skill_scores=scores,
        weak_topics=weak,
        strong_topics=strong
    )
    assert diff2 == "easy"

    # Another struggle on easy -> remains easy (bounded)
    diff3, _, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="easy",
        last_eval_score=3.0,
        current_topic="Databases",
        covered_topics=["Distributed Systems"],
        remaining_topics=[],
        skill_scores=scores,
        weak_topics=weak,
        strong_topics=strong
    )
    assert diff3 == "easy"


def test_difficulty_adaptation_medium_maintenance():
    """Verify medium score (5.0 <= score < 8.0) maintains existing difficulty."""
    diff, _, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="medium",
        last_eval_score=6.8,
        current_topic="SQL",
        covered_topics=[],
        remaining_topics=["APIs"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert diff == "medium"


# ==============================================================================
# D. Topic Selection & Loop Prevention Tests
# ==============================================================================

def test_topic_selection_advances_uncovered_competencies():
    """Verify topic selection pulls next uncovered competency from remaining list."""
    _, next_topic, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="medium",
        last_eval_score=7.5,
        current_topic="Python",
        covered_topics=["Python"],
        remaining_topics=["FastAPI", "SQL", "Redis"],
        skill_scores={},
        weak_topics=[],
        strong_topics=[]
    )
    assert next_topic == "FastAPI"


def test_topic_selection_revisits_weak_topics_when_all_covered():
    """Verify topic selection revisits weak competencies when remaining list is exhausted."""
    _, next_topic, _, _, _ = AdaptiveStateMachine.adapt_difficulty_and_topic(
        current_difficulty="medium",
        last_eval_score=7.0,
        current_topic="Redis",
        covered_topics=["Python", "FastAPI", "Redis"],
        remaining_topics=[],
        skill_scores={"FastAPI": 4.0, "Python": 8.5},
        weak_topics=["FastAPI"],
        strong_topics=["Python"]
    )
    assert next_topic == "FastAPI"


# ==============================================================================
# E. Skill Scoring Tests (Gradual Exponential Smoothing & Bounded)
# ==============================================================================

def test_skill_scoring_gradual_evolution():
    """Verify skill score evolves with 60/40 weighted average and clamps [0, 10]."""
    scores = {}
    # First observation: score = 8.0
    scores = ScoringManager.update_skill_score(scores, "Databases", 8.0)
    assert scores["Databases"] == 8.0

    # Second observation: score = 4.0 -> (0.6 * 4.0) + (0.4 * 8.0) = 2.4 + 3.2 = 5.6
    scores = ScoringManager.update_skill_score(scores, "Databases", 4.0)
    assert scores["Databases"] == 5.6

    # Clamping test
    scores = ScoringManager.update_skill_score(scores, "Databases", 15.0)
    assert scores["Databases"] <= 10.0


# ==============================================================================
# F. Confidence Estimation Tests
# ==============================================================================

def test_confidence_increases_with_evidence_and_observations():
    """Verify confidence is low on single observation and grows with repeated consistent evidence."""
    conf1 = ScoringManager.calculate_confidence(
        topic_observations_count=1,
        evidence_list=["Basic mention of indexing"]
    )
    conf2 = ScoringManager.calculate_confidence(
        topic_observations_count=3,
        evidence_list=["B-Tree depth", "O(log N)", "Composite index ordering"]
    )
    assert conf1 < conf2
    assert 0.1 <= conf1 <= 1.0
    assert 0.1 <= conf2 <= 1.0


def test_confidence_penalized_on_contradictions():
    """Verify confidence is reduced when contradictions or ambiguity exist."""
    conf_clean = ScoringManager.calculate_confidence(2, ["Clear explanation"], has_contradictions=False)
    conf_contradicted = ScoringManager.calculate_confidence(2, ["Conflicting statements"], has_contradictions=True)
    assert conf_contradicted < conf_clean


# ==============================================================================
# G. Question Validation & Duplicate Prevention Tests
# ==============================================================================

def test_duplicate_question_detection():
    """Verify near-identical question text is detected as duplicate."""
    existing = [
        "Explain how database indexes improve query execution speed.",
        "Tell me about a challenging technical disagreement you resolved."
    ]
    assert is_duplicate_question("Explain how database indexes improve query execution speed?", existing) is True
    assert is_duplicate_question("How do database indexes improve query execution speed", existing) is True
    assert is_duplicate_question("How does garbage collection work in Python?", existing) is False


def test_question_data_validation_and_sanitization():
    """Verify validate_question_data sanitizes invalid difficulty, empty text, or missing concepts."""
    raw_invalid = {
        "question_text": "",
        "difficulty": "super_hard",
        "question_type": "unknown_type",
        "expected_concepts": []
    }
    validated = validate_question_data(raw_invalid, default_topic="System Design", default_diff="medium", default_type="technical")
    assert len(validated["question_text"]) > 10
    assert validated["difficulty"] == "medium"
    assert validated["question_type"] == "technical"
    assert len(validated["expected_concepts"]) > 0


# ==============================================================================
# H. Conversational Follow-Up Decision & Probing Tests
# ==============================================================================

def test_follow_up_engine_trigger_cases():
    """Verify FollowUpEngine triggers on vague answers and strong answers on turn 1."""
    # Vague answer (depth < 6.0) -> triggers follow-up
    should_fup, reason = FollowUpEngine.should_follow_up(
        last_eval_score=5.5,
        evidence=["Brief answer"],
        depth_score=4.5,
        turn_count_on_topic=1,
        time_remaining_seconds=600
    )
    assert should_fup is True
    assert reason == "vague_answer"

    # Strong answer (score >= 8.5) -> triggers trade-off probe
    should_fup_strong, reason_strong = FollowUpEngine.should_follow_up(
        last_eval_score=9.0,
        evidence=["Comprehensive breakdown"],
        depth_score=9.0,
        turn_count_on_topic=1,
        time_remaining_seconds=600
    )
    assert should_fup_strong is True
    assert reason_strong == "strong_answer_tradeoffs"

    # Exhausted topic turns (turn >= 3) -> moves on
    should_fup_exhaust, reason_exhaust = FollowUpEngine.should_follow_up(
        last_eval_score=8.5,
        evidence=[],
        depth_score=8.0,
        turn_count_on_topic=3,
        time_remaining_seconds=600
    )
    assert should_fup_exhaust is False
    assert reason_exhaust == "topic_budget_exhausted"


def test_deterministic_follow_up_generation():
    """Verify deterministic fallback follow-up generates context-aware probes."""
    fup_vague = FollowUpEngine.generate_deterministic_follow_up(
        topic="Caching",
        reason_category="vague_answer",
        candidate_answer="We added Redis caching to speed things up."
    )
    assert "invalidation" in fup_vague["question_text"].lower() or "caching" in fup_vague["question_text"].lower()
    assert len(fup_vague["expected_concepts"]) > 0

    fup_strong = FollowUpEngine.generate_deterministic_follow_up(
        topic="Microservices",
        reason_category="strong_answer_tradeoffs",
        candidate_answer="We used gRPC with service mesh for low latency inter-service calls.",
        target_level="senior"
    )
    assert "trade-offs" in fup_strong["question_text"].lower() or "concurrency" in fup_strong["question_text"].lower() or "scale" in fup_strong["question_text"].lower()


# ==============================================================================
# I. Timer Boundaries & Stop Conditions Tests
# ==============================================================================

def test_timer_zero_boundary_enforcement():
    """Verify timer calculation never returns negative values."""
    # Past start time by 40 minutes in a 30-minute interview
    past_start = datetime.utcnow() - timedelta(minutes=40)
    rem = InterviewTimer.calculate_remaining_seconds(past_start, 30)
    assert rem == 0
    assert InterviewTimer.is_expired(past_start, 30) is True

    # Active interview with 10 mins remaining
    active_start = datetime.utcnow() - timedelta(minutes=20)
    rem_active = InterviewTimer.calculate_remaining_seconds(active_start, 30)
    assert 550 <= rem_active <= 650
    assert InterviewTimer.is_expired(active_start, 30) is False


def test_timer_insufficient_time_check():
    """Verify timer flags when remaining time is too short for a complete turn."""
    assert InterviewTimer.has_sufficient_time_for_turn(60, min_seconds=90) is False
    assert InterviewTimer.has_sufficient_time_for_turn(150, min_seconds=90) is True


# ==============================================================================
# J. Full Interview Turn Lifecycle & Engine Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_adaptive_interview_engine_full_lifecycle():
    """Verify AdaptiveInterviewEngine initializes state and processes answer turns."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Mock Role query response
    mock_role = Role(
        id=1,
        company_id=1,
        title="Backend Software Engineer",
        level="entry",
        key_topics=["Database Optimization", "FastAPI APIs", "Distributed Locks"],
        required_skills=["Python", "SQL"]
    )
    mock_res_role = MagicMock()
    mock_res_role.scalars().first.return_value = mock_role
    mock_db.execute.return_value = mock_res_role

    engine = AdaptiveInterviewEngine(mock_db)

    mock_interview = Interview(
        id=10,
        candidate_id=1,
        company_id=1,
        role_id=1,
        duration_minutes=30,
        interview_type="technical",
        target_level="entry",
        status="in_progress",
        start_time=datetime.utcnow()
    )

    # 1. Initialize state
    state = await engine.initialize_interview_state(mock_interview, mock_role.key_topics, initial_question_id=1)
    assert state.interview_id == 10
    assert state.difficulty == "medium"
    assert state.time_remaining_seconds > 0
    assert state.current_topic is not None

    # 2. Process turn with strong answer -> triggers deep dive follow-up
    mock_eval = {
        "correctness_score": 9.0,
        "relevance_score": 9.0,
        "reasoning_score": 8.5,
        "depth_score": 8.5,
        "communication_score": 9.0,
        "overall_question_score": 8.8,
        "evidence": ["Strong B-Tree knowledge"],
        "feedback_text": "Good grasp of query plans."
    }

    state_out, next_q, is_completed = await engine.process_answer_turn(
        interview=mock_interview,
        state=state,
        last_eval_score=8.8,
        asked_question_ids=[1],
        last_eval_dict=mock_eval,
        last_answer_text="B-Trees reduce disk I/O significantly by maintaining sorted balanced tree structure."
    )
    assert is_completed is False
    assert state_out.questions_asked_count == 1
    assert state_out.skill_scores[state.current_topic] >= 8.0


@pytest.mark.asyncio
async def test_question_selector_rag_and_llm_failure_fallbacks():
    """Verify question selector falls back deterministically if RAG or LLM fail."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Question bank returns empty
    mock_res_empty = MagicMock()
    mock_res_empty.scalars().first.return_value = None
    mock_res_empty.all.return_value = []
    mock_db.execute.return_value = mock_res_empty

    selector = QuestionSelector(mock_db)
    selector.rag_engine.get_relevant_context = AsyncMock(side_effect=Exception("RAG down"))

    with patch("app.ai.factory.AIFactory.get_llm_provider") as mock_factory:
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(side_effect=Exception("LLM API timeout"))
        mock_factory.return_value = mock_llm

        q = await selector.select_or_generate_question(
            company_id=1,
            role_id=1,
            topic="Database Indexing",
            difficulty="hard",
            asked_question_ids=[],
            interview_type="technical"
        )
        assert q is not None
        assert "Database Indexing" in q.topic or "Database Indexing" in q.question_text
        assert len(q.question_text) > 10


@pytest.mark.asyncio
async def test_engine_stops_when_insufficient_time_remains():
    """Verify engine transitions to wrapup and completes interview when time is < 90s."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    engine = AdaptiveInterviewEngine(mock_db)

    # Start time was 29.5 minutes ago for a 30-minute interview (remaining ~30s < 90s)
    past_start = datetime.utcnow() - timedelta(minutes=29, seconds=30)
    mock_interview = Interview(
        id=20,
        candidate_id=1,
        company_id=1,
        role_id=1,
        duration_minutes=30,
        interview_type="technical",
        target_level="mid",
        status="in_progress",
        start_time=past_start
    )
    mock_state = InterviewState(
        interview_id=20,
        current_topic="Python",
        difficulty="medium",
        time_remaining_seconds=30,
        questions_asked_count=3,
        current_question_id=5,
        skill_scores={"Python": 7.0},
        weak_topics=[],
        strong_topics=[],
        covered_topics=[],
        remaining_topics=["SQL"],
        interview_stage="core"
    )

    state_out, next_q, is_completed = await engine.process_answer_turn(
        interview=mock_interview,
        state=mock_state,
        last_eval_score=7.5,
        asked_question_ids=[5]
    )
    assert is_completed is True
    assert state_out.interview_stage == "wrapup"
    assert next_q is None
    assert mock_interview.status == "completed"

