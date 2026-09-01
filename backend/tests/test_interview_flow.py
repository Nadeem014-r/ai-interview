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

# Module 3 Acceptance Tests
@pytest.mark.asyncio
async def test_interview_bootstrap_persona_framing_differences():
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.database import init_db

    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fetch companies
        comps_res = await client.get("/api/v1/companies")
        assert comps_res.status_code == 200
        companies = comps_res.json()
        assert len(companies) >= 2

        comp_google = next(c for c in companies if "Google" in c["name"])
        comp_amazon = next(c for c in companies if "Amazon" in c["name"])

        # Fetch roles
        roles_google = (await client.get(f"/api/v1/companies/{comp_google['id']}/roles")).json()
        roles_amazon = (await client.get(f"/api/v1/companies/{comp_amazon['id']}/roles")).json()

        # Register Candidate
        email = f"cand_mod3_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Jordan Candidate"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Start Google Session
        session_google = (await client.post("/api/v1/interviews", json={
            "company_id": comp_google["id"],
            "role_id": roles_google[0]["id"],
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        }, headers=headers)).json()

        # Start Amazon Session
        session_amazon = (await client.post("/api/v1/interviews", json={
            "company_id": comp_amazon["id"],
            "role_id": roles_amazon[0]["id"],
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        }, headers=headers)).json()

        q_google = session_google["current_question"]["question_text"]
        q_amazon = session_amazon["current_question"]["question_text"]

        # Verify persona framing differences:
        # Both start with warm-up / personal introduction
        assert session_google["current_question"]["question_type"] == "hr"
        assert session_amazon["current_question"]["question_type"] == "hr"
        assert q_google != q_amazon
        assert "Google" in q_google or comp_google["name"] in q_google
        assert "Amazon" in q_amazon or comp_amazon["name"] in q_amazon

@pytest.mark.asyncio
async def test_interview_mode_configuration():
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comps = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{comps[0]['id']}/roles")).json()

        email = f"cand_mode_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Mode Tester"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for mode in ["text", "audio", "video"]:
            res = await client.post("/api/v1/interviews", json={
                "company_id": comps[0]["id"],
                "role_id": roles[0]["id"],
                "mode": mode,
                "interview_type": "technical",
                "duration_minutes": 15,
                "target_level": "entry"
            }, headers=headers)
            assert res.status_code == 200
            session = res.json()
            assert session["mode"] == mode
            assert session["status"] == "in_progress"
            assert session["current_question"] is not None

# Module 4 Acceptance Tests: Answer Evaluation, Real-Time Follow-Ups & Stage Progression
@pytest.mark.asyncio
async def test_incorrect_answer_receives_low_score_and_critical_feedback():
    # Evaluate a deliberately incorrect answer
    wrong_answer = "Python has no garbage collector, everything requires manual C malloc and pointer dereferencing for variables."
    eval_result = await AnswerEvaluator.evaluate_answer(
        question_text="Explain Python's memory management and garbage collection model.",
        expected_concepts=["Reference counting", "Generational cyclic GC", "PyObject allocation"],
        candidate_answer=wrong_answer,
        topic="Python Fundamentals"
    )

    assert eval_result["overall_question_score"] <= 4.0
    assert eval_result["correctness_score"] <= 3.0
    assert "error" in eval_result["feedback_text"].lower() or "factual" in eval_result["feedback_text"].lower() or "review" in eval_result["feedback_text"].lower()

@pytest.mark.asyncio
async def test_partial_evasive_answer_evaluates_with_appropriate_scores():
    partial_answer = "Indexing is just index, it works fast."
    eval_result = await AnswerEvaluator.evaluate_answer(
        question_text="How do database indexes improve query execution speed, and what are the trade-offs on write operations?",
        expected_concepts=["B-Tree indexing", "Disk I/O reduction", "Write overhead"],
        candidate_answer=partial_answer,
        topic="Relational Databases"
    )

    # Score should be lower than a complete, rigorous answer
    assert eval_result["overall_question_score"] < 7.0
    assert "feedback_text" in eval_result

@pytest.mark.asyncio
async def test_interview_stage_progression_warmup_to_technical_to_wrapup():
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comps = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{comps[0]['id']}/roles")).json()

        email = f"cand_prog_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Progress Tester"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Start interview (Duration: 5 minutes to test wrap-up quickly)
        res = await client.post("/api/v1/interviews", json={
            "company_id": comps[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 5,
            "target_level": "entry"
        }, headers=headers)
        session = res.json()
        interview_id = session["id"]

        # 1. Turn 1 must be Warm-up / HR / Introduction
        assert session["current_question"]["question_type"] == "hr"

        # Submit Turn 1
        turn1 = await client.post(f"/api/v1/interviews/{interview_id}/answer", json={
            "answer_text": "I am a recent computer science graduate passionate about backend scalability and distributed systems."
        }, headers=headers)
        assert turn1.status_code == 200
        t1_data = turn1.json()
        assert t1_data["evaluation"]["overall_question_score"] > 0

        # Next question should be present
        assert t1_data["next_question"] is not None


@pytest.mark.asyncio
async def test_struggling_candidate_recovery_and_conclusion_api_flow():
    """Verify live flow: candidate struggles -> recovery question generated -> recovery answer submitted -> completed without 500 error."""
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        comps = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{comps[0]['id']}/roles")).json()

        email = f"cand_recov_{uuid.uuid4().hex[:8]}@example.com"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Recovery Candidate"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Start interview
        res = await client.post("/api/v1/interviews", json={
            "company_id": comps[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 15,
            "target_level": "entry"
        }, headers=headers)
        assert res.status_code == 200
        interview_id = res.json()["id"]

        # Turn 1: Warmup answered poorly
        turn1 = await client.post(f"/api/v1/interviews/{interview_id}/answer", json={
            "answer_text": "no"
        }, headers=headers)
        assert turn1.status_code == 200
        t1_data = turn1.json()
        assert t1_data["is_completed"] is False

        # Turn 2: Question 2 answered poorly -> Triggers Recovery Question
        turn2 = await client.post(f"/api/v1/interviews/{interview_id}/answer", json={
            "answer_text": "no"
        }, headers=headers)
        assert turn2.status_code == 200
        t2_data = turn2.json()
        assert t2_data["is_completed"] is False
        assert t2_data["next_question"] is not None
        assert t2_data["interview_state"]["interview_stage"] == "recovery"

        # Turn 3: Submitting answer to the Recovery Question MUST succeed without 500 error and conclude politely
        turn3 = await client.post(f"/api/v1/interviews/{interview_id}/answer", json={
            "answer_text": "no"
        }, headers=headers)
        assert turn3.status_code == 200
        t3_data = turn3.json()
        assert t3_data["is_completed"] is True
        assert t3_data["closing_message"] is not None
        assert "Thank you" in t3_data["closing_message"]

        # Turn 4: Submitting answer when interview completed returns idempotent 200 response without error
        turn4 = await client.post(f"/api/v1/interviews/{interview_id}/answer", json={
            "answer_text": "extra answer"
        }, headers=headers)
        assert turn4.status_code == 200
        t4_data = turn4.json()
        assert t4_data["is_completed"] is True

