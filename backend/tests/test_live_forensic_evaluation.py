"""Phase 11-14: Forensic Evaluation & Live Adaptive Behavior Regression Tests.

Verifies:
1. Exact bug regression: 'shdfghj' on HR/Technical question scores <= 1.5 with quality 'unknown' and action 'recover'
2. Adversarial inputs: gibberish, non-language, evasive, off-topic, short-correct, expert, misconceptions
3. Human-like natural interviewer questions without internal metadata or robotic templates
4. Real API multi-turn sequence execution via POST /api/v1/interviews/{id}/answer
"""

import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal, init_db
from app.db.models import User, Company, Role, Interview, InterviewState, Question, Answer, Evaluation
from app.evaluation.evaluator import AnswerEvaluator
from app.interview.conversation import FollowUpEngine
from app.interview.question_selector import is_duplicate_question
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_exact_live_bug_regression():
    """PHASE 11: Exact regression test for live failure."""
    question_text = "You touched on Introduction & Motivation. Can you explain Specific role motivation and relevant projects in more detail and how it impacts system behavior?"
    candidate_answer = "shdfghj"

    res = await AnswerEvaluator.evaluate_answer(
        question_text=question_text,
        expected_concepts=["Role motivation", "Relevant project experience"],
        candidate_answer=candidate_answer,
        topic="Introduction & Motivation",
        question_type="hr"
    )

    assert res["overall_question_score"] <= 1.5, f"Expected score <= 1.5, got {res['overall_question_score']}"
    assert res["answer_quality"] == "unknown", f"Expected quality 'unknown', got {res['answer_quality']}"
    assert res["recommended_action"] == "recover", f"Expected action 'recover', got {res['recommended_action']}"
    
    # Assert NO false praise
    forbidden_praise = ["good", "great", "excellent", "strong", "well done"]
    fb_lower = res["feedback_text"].lower()
    for praise in forbidden_praise:
        assert praise not in fb_lower, f"Feedback contained false praise '{praise}': {res['feedback_text']}"


@pytest.mark.asyncio
async def test_adversarial_gibberish_evaluations():
    """PHASE 12: Adversarial inputs across all states."""
    # 1. "shdfghj"
    res1 = await AnswerEvaluator.evaluate_answer(
        question_text="Why would you choose a linked list instead of an array?",
        expected_concepts=["Dynamic sizing", "Insertion cost O(1)", "No contiguous allocation"],
        candidate_answer="shdfghj",
        topic="Data Structures",
        question_type="technical"
    )
    assert res1["overall_question_score"] <= 1.5
    assert res1["answer_quality"] == "unknown"
    assert res1["recommended_action"] == "recover"

    # 2. "asdfgh qwerty"
    res2 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="asdfgh qwerty",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res2["overall_question_score"] <= 1.5
    assert res2["answer_quality"] == "unknown"

    # 3. "blah blah blah"
    res3 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="blah blah blah",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res3["overall_question_score"] <= 1.5
    assert res3["answer_quality"] == "unknown"

    # 4. "I don't know."
    res4 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="I don't know.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res4["overall_question_score"] <= 1.5
    assert res4["answer_quality"] == "unknown"
    assert res4["recommended_action"] == "recover"

    # 5. "Paris is the capital of France." on DB question
    res5 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="Paris is the capital of France.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res5["overall_question_score"] <= 1.5
    assert res5["relevance_score"] <= 1.0
    assert res5["answer_quality"] in ["unknown", "weak"]
    assert res5["recommended_action"] == "recover"

    # 6. "Indexing makes database queries faster." -> Partial
    res6 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="Indexing makes database queries faster.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert 4.5 <= res6["overall_question_score"] <= 7.0
    assert res6["answer_quality"] == "partial"
    assert res6["recommended_action"] == "follow_up"

    # 7. "Indexes use B+ trees and reduce the amount of data scanned, but they require extra storage and increase write cost." -> Strong
    res7 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain database index trade-offs.",
        expected_concepts=["B+ Tree", "Disk I/O", "Write overhead"],
        candidate_answer="Indexes use B+ trees and reduce the amount of data scanned, but they require extra storage and increase write cost.",
        topic="Database Indexing",
        question_type="technical"
    )
    assert res7["overall_question_score"] >= 8.0
    assert res7["answer_quality"] in ["strong", "excellent"]
    assert res7["recommended_action"] == "deepen"

    # 8. Long incorrect answer
    res8 = await AnswerEvaluator.evaluate_answer(
        question_text="Explain JWT authentication security.",
        expected_concepts=["Signature verification", "Payload encoding", "Stateless auth"],
        candidate_answer="JWT tokens are fully encrypted using military-grade RSA 4096-bit encryption so nobody can ever see the payload data, and they maintain a permanent TCP socket to the database server.",
        topic="API Security",
        question_type="technical"
    )
    assert res8["overall_question_score"] <= 3.5
    assert res8["answer_quality"] == "incorrect"
    assert res8["recommended_action"] == "clarify"

    # 9. Short but technically correct answer: "Arrays allow constant-time indexed access."
    res9 = await AnswerEvaluator.evaluate_answer(
        question_text="What is the primary advantage of an array over a linked list?",
        expected_concepts=["Constant-time indexed access", "Cache locality"],
        candidate_answer="Arrays allow constant-time indexed access.",
        topic="Data Structures",
        question_type="technical"
    )
    assert res9["overall_question_score"] >= 6.5
    assert res9["correctness_score"] >= 7.5
    assert res9["answer_quality"] in ["partial", "strong"]

    # 10. Semantically relevant answer without literal expected keywords
    res10 = await AnswerEvaluator.evaluate_answer(
        question_text="How do hash tables work?",
        expected_concepts=["Hash function", "Buckets", "Collisions"],
        candidate_answer="They compute an integer position from the input key using arithmetic and store the value in an internal slot array.",
        topic="Data Structures",
        question_type="technical"
    )
    assert res10["overall_question_score"] >= 5.0


def test_question_generation_naturalness_and_clean_dialogue():
    """PHASE 13: Question generation tests."""
    # 1. Natural spoken question for HR recovery
    q_hr_rec = FollowUpEngine.generate_deterministic_follow_up(
        topic="Introduction & Motivation",
        reason_category="recover",
        candidate_answer="shdfghj"
    )
    text = q_hr_rec["question_text"]
    assert "Focus:" not in text
    assert "system behavior" not in text
    assert "demonstrated concepts" not in text
    assert "missing concepts" not in text
    assert "target level" not in text
    assert "role" in text.lower() or "background" in text.lower()

    # 2. Natural spoken question for project probe
    q_hr_proj = FollowUpEngine.generate_deterministic_follow_up(
        topic="Introduction & Motivation",
        reason_category="probe_missing",
        candidate_answer="I built a full stack app using React."
    )
    assert "React" in q_hr_proj["question_text"]
    assert "system behavior" not in q_hr_proj["question_text"]

    # 3. Technical deep dive probe
    q_tech_deep = FollowUpEngine.generate_deterministic_follow_up(
        topic="Database Indexing",
        reason_category="strong_answer_tradeoffs",
        candidate_answer="B+ trees reduce disk I/O."
    )
    assert "concurrency" in q_tech_deep["question_text"].lower() or "scale" in q_tech_deep["question_text"].lower() or "write amplification" in q_tech_deep["question_text"].lower()


@pytest.mark.asyncio
async def test_live_api_multi_turn_sequence():
    """PHASE 14: Real API multi-turn sequence on POST /api/v1/interviews/{id}/answer."""
    await init_db()

    async with AsyncSessionLocal() as session:
        uid = uuid.uuid4().hex[:10]
        company = Company(name=f"ForensicCorp_{uid}", slug=f"fcorp_{uid}", description="Forensic test company")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        role = Role(
            company_id=company.id,
            title="Backend Engineer",
            level="entry",
            key_topics=["Introduction & Motivation", "Database Indexing", "Data Structures", "API Security"]
        )
        session.add(role)
        await session.commit()
        await session.refresh(role)

        user = User(
            email=f"forensic_{uid}@edu.com",
            hashed_password="hashed_pw",
            full_name="Forensic Candidate",
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
            start_time=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        q1 = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Introduction & Motivation",
            difficulty="easy",
            question_type="hr",
            question_text="Welcome! To start off, could you introduce yourself and tell me what interests you about this role?",
            expected_concepts=["Personal introduction", "Role motivation"]
        )
        session.add(q1)
        await session.commit()
        await session.refresh(q1)

        state = InterviewState(
            interview_id=interview.id,
            current_topic="Introduction & Motivation",
            difficulty="easy",
            time_remaining_seconds=1800,
            questions_asked_count=0,
            current_question_id=q1.id,
            skill_scores={},
            weak_topics=[],
            strong_topics=[],
            covered_topics=[],
            remaining_topics=["Database Indexing", "Data Structures", "API Security"],
            interview_stage="intro"
        )
        session.add(state)
        await session.commit()

        token = create_access_token(subject=user.id, role=user.role)

    # Execute 5 live API turns against /api/v1/interviews/{id}/answer
    turns_payload = [
        # Turn 1: Candidate types "shdfghj" on Introduction & Motivation (THE EXACT REPORTED BUG)
        ("shdfghj", 0.0, 1.5),
        # Turn 2: Proper introduction and background
        ("I am a computer science graduate interested in backend engineering and building scalable APIs with Python and FastAPI.", 6.5, 9.5),
        # Turn 3: Strong technical answer on Database Indexing
        ("Database indexes organize data into B+ trees to reduce disk I/O to O(log N), trading off write throughput and storage.", 7.5, 10.0),
        # Turn 4: "I don't know."
        ("I don't know.", 0.0, 1.5),
        # Turn 5: Partial answer on Data Structures
        ("Hashing distributes keys into buckets using a hash function to map keys to values.", 4.5, 7.5)
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        for turn_idx, (answer_text, min_expected_score, max_expected_score) in enumerate(turns_payload, start=1):
            res = await client.post(
                f"/api/v1/interviews/{interview.id}/answer",
                json={"answer_text": answer_text},
                headers=headers
            )
            assert res.status_code == 200, f"Turn {turn_idx} failed: {res.text}"
            data = res.json()

            eval_res = data["evaluation"]
            score = eval_res["overall_question_score"]
            quality = eval_res["answer_quality"]
            action = eval_res["recommended_action"]
            provider = eval_res.get("provider_used", "mock")

            print(f"\n[TURN {turn_idx}] Answer: '{answer_text}' -> Score: {score}, Quality: {quality}, Action: {action}")
            if data.get("next_question"):
                print(f"  Next Q: {data['next_question']['question_text']} (Topic: {data['next_question']['topic']}, Type: {data['next_question']['question_type']})")

            assert min_expected_score <= score <= max_expected_score, (
                f"Turn {turn_idx} ('{answer_text[:20]}...') score {score} not in [{min_expected_score}, {max_expected_score}]"
            )

            if turn_idx == 1:
                # TURN 1: "shdfghj" MUST score <= 1.5, quality unknown, action recover
                assert score <= 1.5
                assert quality == "unknown"
                assert action == "recover"
                # The written feedback is no longer handed to the candidate
                # mid-interview, so read the persisted evaluation instead: what
                # matters is that gibberish is never praised in what was stored.
                from sqlalchemy import select as _select
                async with AsyncSessionLocal() as _db:
                    _fb = (await _db.execute(
                        _select(Evaluation.feedback_text)
                        .join(Answer, Answer.id == Evaluation.answer_id)
                        .where(Answer.interview_id == interview.id)
                        .order_by(Evaluation.id.desc())
                    )).scalars().first()
                assert _fb is not None
                assert "good" not in _fb.lower()

            if turn_idx == 4:
                # TURN 4: "I don't know." MUST score <= 1.5, quality unknown, action recover
                assert score <= 1.5
                assert quality == "unknown"
                assert action == "recover"

            if turn_idx < 5:
                assert data.get("next_question") is not None
                assert data.get("is_completed") is False
            else:
                assert data.get("is_completed") in [True, False]
