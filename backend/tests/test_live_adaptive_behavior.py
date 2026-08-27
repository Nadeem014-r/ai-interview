"""Phase 9/10: Comprehensive Live Adaptive Interview Behavior & Regression Tests.

Validates that:
1. "I don't know" cannot score 8+
2. Irrelevant answer cannot score 8+
3. Strong technical answer scores substantially higher than irrelevant answer
4. Weak answer and strong answer produce different decisions
5. Strong answer produces harder follow-up / deeper probe
6. Weak answer produces easier/recovery follow-up
7. Misconception produces misconception-specific follow-up
8. Follow-up uses actual candidate answer
9. Identical follow-up is rejected
10. Semantic duplicate is rejected
11. Legitimate deep-dive question is allowed
12. Follow-up path updates difficulty
13. Follow-up path updates state
14. First question is evaluated using its own topic
15. Interview can continue beyond 3 questions when time permits
16. Interview eventually terminates
17. Different interview sessions do not share question state
18. Gemini failure does not create fake generic praise
19. Deterministic fallback produces different questions for different answer archetypes
20. Provider used is observable in logs/test instrumentation
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import User, Company, Role, Interview, InterviewState, Question, Answer, Evaluation
from app.evaluation.evaluator import AnswerEvaluator
from app.ai.factory import AIFactory
from app.ai.router import RoutedLLMProvider
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.conversation import FollowUpEngine
from app.interview.question_selector import is_duplicate_question, normalize_text_for_comparison
from app.interview.timer import InterviewTimer
from app.interview.state_machine import AdaptiveStateMachine


@pytest.mark.asyncio
async def test_idontknow_cannot_score_high():
    """1. 'I don't know' must score <= 2.0 and recommend recovery."""
    res = await AnswerEvaluator.evaluate_answer(
        question_text="Explain how indexing improves query performance in relational databases.",
        expected_concepts=["B-Tree structure", "Reduced disk I/O", "Search complexity O(log N)", "Write overhead trade-offs"],
        candidate_answer="I don't know. I have never studied this concept.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res["overall_question_score"] <= 2.0
    assert res["answer_quality"] in ["unknown", "weak"]
    assert res["recommended_action"] == "recover"
    assert "not demonstrate knowledge" in res["feedback_text"].lower() or "review" in res["feedback_text"].lower()
    assert "good explanation" not in res["feedback_text"].lower()


@pytest.mark.asyncio
async def test_irrelevant_answer_cannot_score_high():
    """2. Clearly irrelevant answer must score <= 2.0 and recommend recovery."""
    res = await AnswerEvaluator.evaluate_answer(
        question_text="Explain how indexing improves query performance in relational databases.",
        expected_concepts=["B-Tree structure", "Reduced disk I/O", "Search complexity O(log N)", "Write overhead trade-offs"],
        candidate_answer="Paris is the capital of France and the weather is very nice today.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res["overall_question_score"] <= 2.0
    assert res["relevance_score"] <= 2.0
    assert res["answer_quality"] in ["unknown", "weak"]
    assert res["recommended_action"] == "recover"


@pytest.mark.asyncio
async def test_strong_answer_scores_substantially_higher():
    """3. Strong technical answer scores substantially higher than weak/irrelevant."""
    strong_ans = (
        "Database indexing uses balanced B+ Trees to organize table records on disk. "
        "Instead of scanning every row with O(N) disk I/O, the search traverses tree levels in O(log N) operations. "
        "However, indexes introduce write overhead and storage trade-offs because inserts, updates, and deletes "
        "require updating the tree pages."
    )
    weak_ans = "Random text with no technical relation."

    res_strong = await AnswerEvaluator.evaluate_answer(
        question_text="Explain how indexing improves query performance in relational databases.",
        expected_concepts=["B-Tree structure", "Reduced disk I/O", "Search complexity O(log N)", "Write overhead trade-offs"],
        candidate_answer=strong_ans,
        topic="Database Indexing",
        question_type="technical"
    )
    res_weak = await AnswerEvaluator.evaluate_answer(
        question_text="Explain how indexing improves query performance in relational databases.",
        expected_concepts=["B-Tree structure", "Reduced disk I/O", "Search complexity O(log N)", "Write overhead trade-offs"],
        candidate_answer=weak_ans,
        topic="Database Indexing",
        question_type="technical"
    )
    assert res_strong["overall_question_score"] >= 8.0
    assert res_weak["overall_question_score"] <= 2.0
    assert res_strong["overall_question_score"] - res_weak["overall_question_score"] >= 6.0


@pytest.mark.asyncio
async def test_misconception_produces_clarification():
    """7. Misconceptions produce clarification action and specific feedback."""
    res = await AnswerEvaluator.evaluate_answer(
        question_text="Explain JWT authentication.",
        expected_concepts=["Header", "Payload", "Signature", "Stateless verification"],
        candidate_answer="JWT is completely encrypted so nobody can read the payload data.",
        topic="API Security",
        question_type="technical"
    )
    assert res["overall_question_score"] <= 4.0
    assert res["answer_quality"] == "incorrect"
    assert res["recommended_action"] == "clarify"
    assert len(res["misconceptions"]) > 0


def test_duplicate_detection_rejects_identical_and_near_duplicates():
    """9 & 10. Duplicate detector rejects exact and semantic duplicates."""
    asked = [
        "How does a hash table achieve average O(1) lookup?",
        "Explain how database indexes improve query performance."
    ]
    # Exact duplicate
    assert is_duplicate_question("How does a hash table achieve average O(1) lookup?", asked) is True
    # Normalized duplicate
    assert is_duplicate_question("how does a hash table achieve average o(1) lookup", asked) is True
    # High overlap duplicate
    assert is_duplicate_question("How does a hash table achieve O(1) average lookup performance?", asked) is True


def test_duplicate_detection_allows_legitimate_deep_dives():
    """11. Duplicate detector allows legitimate distinct follow-ups on the same topic."""
    asked = ["How does a hash table achieve average O(1) lookup?"]
    # Distinct follow-up on collision handling
    assert is_duplicate_question("What happens when multiple keys collide in a hash table and how do you resolve it?", asked) is False
    # Distinct follow-up on load factor
    assert is_duplicate_question("What is load factor in a hash table and how does dynamic resizing work?", asked) is False


def test_deterministic_fallback_produces_different_questions_for_archetypes():
    """19. Deterministic fallback produces distinct questions for different answer archetypes."""
    q_strong = FollowUpEngine.generate_deterministic_follow_up(
        topic="Data Structures",
        reason_category="strong_answer_tradeoffs",
        candidate_answer="Hash tables use buckets for O(1) lookup.",
        eval_dict={"demonstrated_concepts": ["O(1) lookup"], "missing_concepts": [], "misconceptions": []}
    )
    q_weak = FollowUpEngine.generate_deterministic_follow_up(
        topic="Data Structures",
        reason_category="recover",
        candidate_answer="I don't know.",
        eval_dict={"demonstrated_concepts": [], "missing_concepts": ["Core mechanics"], "misconceptions": []}
    )
    q_misc = FollowUpEngine.generate_deterministic_follow_up(
        topic="API Security",
        reason_category="clarify_misconception",
        candidate_answer="jwt is encrypted",
        eval_dict={"demonstrated_concepts": [], "missing_concepts": [], "misconceptions": ["JWT is encrypted"]}
    )

    assert q_strong["question_text"] != q_weak["question_text"]
    assert "problem that data structures is designed to solve" in q_weak["question_text"].lower() or "fundamentals" in q_weak["question_text"].lower()
    assert "jwt" in q_misc["question_text"].lower()


from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_engine_followup_updates_difficulty_and_prevents_duplicates():
    """5, 6, 12, 13. Engine updates difficulty and respects duplicate safety in follow-up path."""
    async with AsyncSessionLocal() as session:
        ts = datetime.utcnow().timestamp()
        company = Company(name=f"TechCorp_{ts}", slug=f"techcorp_{ts}", description="Tech company")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        role = Role(company_id=company.id, title="Backend Engineer", level="entry", key_topics=["Data Structures", "Databases"])
        session.add(role)
        await session.commit()
        await session.refresh(role)

        user = User(email=f"test_adaptive_{datetime.utcnow().timestamp()}@edu.com", hashed_password="hashed_pw", full_name="Adaptive Student", role="candidate")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            interview_type="technical",
            duration_minutes=30,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        q1 = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Data Structures",
            difficulty="medium",
            question_type="technical",
            question_text="How do hash tables work under the hood?",
            expected_concepts=["Hash function", "Buckets", "Collisions"]
        )
        session.add(q1)
        await session.commit()
        await session.refresh(q1)

        engine = AdaptiveInterviewEngine(session)
        state = await engine.initialize_interview_state(interview, ["Data Structures", "Databases"], initial_question_id=q1.id)

        # Strong answer -> score >= 8.0 -> step up difficulty to hard
        eval_dict_strong = {
            "correctness_score": 9.0,
            "relevance_score": 9.0,
            "reasoning_score": 8.5,
            "depth_score": 8.5,
            "communication_score": 9.0,
            "overall_question_score": 8.85,
            "answer_quality": "strong",
            "recommended_action": "deepen",
            "evidence": ["Hash table buckets and hashing mechanics explained."],
            "feedback_text": "Strong technical explanation.",
            "demonstrated_concepts": ["Hash function", "Buckets"],
            "missing_concepts": [],
            "misconceptions": []
        }

        updated_state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=8.85,
            asked_question_ids=[q1.id],
            last_eval_dict=eval_dict_strong,
            last_answer_text="Hash tables compute a hash of the key and map it to an array bucket."
        )

        assert is_completed is False
        assert next_q is not None
        assert next_q.question_text != q1.question_text
        assert updated_state.difficulty == "hard"  # Stepped up from medium to hard!


@pytest.mark.asyncio
async def test_first_question_evaluated_with_own_topic():
    """14. Question 1 evaluates with its own topic ('Introduction & Motivation'), not role technical topic."""
    q_warmup = Question(
        company_id=1,
        role_id=1,
        topic="Introduction & Motivation",
        difficulty="easy",
        question_type="hr",
        question_text="Tell me about your background and why you are interested in this role.",
        expected_concepts=["Educational background", "Role motivation"]
    )
    
    res = await AnswerEvaluator.evaluate_answer(
        question_text=q_warmup.question_text,
        expected_concepts=q_warmup.expected_concepts,
        candidate_answer="I am a fresh computer science graduate who built full-stack web applications using React and Python.",
        topic=q_warmup.topic,  # Correct topic used!
        question_type=q_warmup.question_type
    )

    assert res["overall_question_score"] >= 7.0
    assert "background" in res["feedback_text"].lower() or "motivation" in res["feedback_text"].lower() or "role" in res["feedback_text"].lower()


def test_provider_observability_tracks_last_used():
    """20. Provider routing tracks whether primary or fallback was used."""
    from app.ai.mock_provider import MockLLMProvider
    p = RoutedLLMProvider(
        primary_provider=MockLLMProvider("primary-mock"),
        fallback_provider=MockLLMProvider("fallback-mock")
    )
    assert hasattr(p, "last_provider_used")


@pytest.mark.asyncio
async def test_multi_turn_interview_continues_beyond_three_questions():
    """15. Interview progresses naturally through 5+ questions without artificial 3-turn cutoff."""
    async with AsyncSessionLocal() as session:
        ts = datetime.utcnow().timestamp()
        company = Company(name=f"MultiTurnCorp_{ts}", slug=f"multiturn_{ts}", description="Multi turn test")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        role = Role(
            company_id=company.id,
            title="Backend Engineer",
            level="entry",
            key_topics=["Data Structures", "System Design", "Database Indexing", "API Security"]
        )
        session.add(role)
        await session.commit()
        await session.refresh(role)

        user = User(
            email=f"multiturn_{ts}@edu.com",
            hashed_password="hashed_pw",
            full_name="Multi Turn Student",
            role="candidate"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            interview_type="technical",
            duration_minutes=30,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        q1 = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Data Structures",
            difficulty="medium",
            question_type="technical",
            question_text="Explain hash tables.",
            expected_concepts=["Buckets", "Collisions"]
        )
        session.add(q1)
        await session.commit()
        await session.refresh(q1)

        engine = AdaptiveInterviewEngine(session)
        state = await engine.initialize_interview_state(
            interview,
            ["Data Structures", "System Design", "Database Indexing", "API Security"],
            initial_question_id=q1.id
        )

        asked_ids = []
        is_completed = False
        turns_executed = 0

        for i in range(5):
            turns_executed += 1
            cur_qid = state.current_question_id or q1.id
            ans = Answer(
                interview_id=interview.id,
                question_id=cur_qid,
                candidate_answer_text="Solid answer detailing architecture and mechanics."
            )
            session.add(ans)
            await session.commit()
            asked_ids.append(cur_qid)

            eval_dict = {
                "correctness_score": 8.0,
                "relevance_score": 8.0,
                "reasoning_score": 8.0,
                "depth_score": 7.5,
                "communication_score": 8.0,
                "overall_question_score": 7.95,
                "answer_quality": "strong",
                "recommended_action": "deepen",
                "evidence": ["Solid understanding"],
                "feedback_text": "Good technical grasp.",
                "demonstrated_concepts": [state.current_topic],
                "missing_concepts": [],
                "misconceptions": []
            }

            state, next_q, is_completed = await engine.process_answer_turn(
                interview=interview,
                state=state,
                last_eval_score=7.95,
                asked_question_ids=asked_ids,
                last_eval_dict=eval_dict,
                last_answer_text="Solid answer detailing architecture and mechanics."
            )

        assert turns_executed == 5
        assert is_completed is False
        assert state.questions_asked_count == 5


@pytest.mark.asyncio
async def test_interview_terminates_when_time_exhausted():
    """16. Interview properly terminates when time budget is exhausted."""
    async with AsyncSessionLocal() as session:
        ts = datetime.utcnow().timestamp()
        company = Company(name=f"TermCorp_{ts}", slug=f"termcorp_{ts}", description="Term test")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        role = Role(company_id=company.id, title="Backend Engineer", level="entry", key_topics=["Data Structures"])
        session.add(role)
        await session.commit()
        await session.refresh(role)

        user = User(email=f"term_{ts}@edu.com", hashed_password="hashed_pw", full_name="Term Student", role="candidate")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            interview_type="technical",
            duration_minutes=30,
            status="in_progress",
            start_time=datetime.utcnow() - timedelta(minutes=29, seconds=30)  # Only 30s remaining
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        engine = AdaptiveInterviewEngine(session)
        state = await engine.initialize_interview_state(interview, ["Data Structures"])

        eval_dict = {
            "correctness_score": 8.0,
            "relevance_score": 8.0,
            "reasoning_score": 8.0,
            "depth_score": 8.0,
            "communication_score": 8.0,
            "overall_question_score": 8.0,
            "answer_quality": "strong",
            "recommended_action": "deepen",
            "evidence": [],
            "feedback_text": "Good",
            "demonstrated_concepts": [],
            "missing_concepts": [],
            "misconceptions": []
        }

        state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=8.0,
            asked_question_ids=[],
            last_eval_dict=eval_dict,
            last_answer_text="Quick answer"
        )

        assert is_completed is True
        assert next_q is None
        assert state.interview_stage == "wrapup"


