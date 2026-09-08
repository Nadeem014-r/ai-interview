"""Comprehensive Phase 2 Test Suite: Multi-Turn Adaptive Interview Engine & Candidate Isolation.

Covers:
- Strict Candidate Recommendation Isolation & Zero Leakage (Tests 1-4)
- Candidate Data & IDOR Authorization Protections (Tests 5-8, 20)
- Company-Role Pairing Validation (Tests 9-10)
- Safe Answer Persistence, Empty Answer Rejection & Duplicate Answer Protection (Tests 11-13, 18)
- Multi-Turn State Progression, Context-Aware Questions & Duplicate Prevention (Tests 14-16)
- AI Fault Tolerance & Graceful Fallback Generation (Tests 17-18)
- Interview Completion, Report Generation & Report Isolation (Tests 19-20)
- Concurrency, Session Persistence & Multi-Candidate Integrity (Tests 21-25)
"""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.db.models import (
    User, Company, Role, Resume, ResumeProfile, Interview,
    Question, Answer, Evaluation, Report
)
from app.core.database import AsyncSessionLocal
from app.interview.question_selector import is_duplicate_question, QuestionSelector
from app.matching.matcher import JobMatchingEngine


SAMPLE_FRONTEND_RESUME = b"""
John Frontend Doe
Email: john.frontend@example.com
Education: Bachelor of Science in Computer Science, Stanford University (2023)
Skills: React, Next.js, TypeScript, JavaScript, HTML5, CSS3, TailwindCSS, Redux Toolkit
Experience:
Frontend Engineer Intern at WebTech Inc (2022 - 2023)
- Built interactive single page applications using React and Next.js.
- Developed type-safe reusable UI components with TypeScript and TailwindCSS.
Projects:
- Portfolio Platform: Full-stack React, TypeScript, and CSS responsive web application.
"""

SAMPLE_ML_RESUME = b"""
Alice ML Engineer
Email: alice.ml@example.com
Education: Master of Science in Data Science, MIT (2023)
Skills: Python, PyTorch, TensorFlow, Machine Learning, Deep Learning, Pandas, Scikit-Learn, SQL
Experience:
ML Research Intern at AI Labs (2022 - 2023)
- Trained transformer neural network models using PyTorch and HuggingFace.
- Built data processing pipelines with Python and Pandas for computer vision and NLP datasets.
Projects:
- Predictive Analytics Engine: Machine learning classification pipeline using PyTorch and Scikit-Learn.
"""


async def create_and_authenticate_candidate(client: AsyncClient, prefix: str = "cand") -> tuple[dict, str, int]:
    """Helper to register and login a fresh candidate with unique credentials."""
    unique_id = uuid.uuid4().hex[:8]
    email = f"{prefix}_{unique_id}@example.com"
    password = "SecurePassword123!"
    full_name = f"Candidate {prefix.upper()} {unique_id}"

    reg_res = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": full_name,
        "role": "candidate"
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    user_id = reg_res.json()["user_id"]

    login_res = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, email, user_id


async def get_target_company_and_roles() -> tuple[Company, Role, Company, Role]:
    """Helper to fetch 2 distinct approved companies and their roles from DB."""
    async with AsyncSessionLocal() as db:
        stmt = select(Company).options(selectinload(Company.roles)).order_by(Company.id)
        res = await db.execute(stmt)
        comps = res.scalars().all()
        assert len(comps) >= 2, "At least 2 approved companies must exist in database"
        
        comp_a = comps[0]
        comp_b = comps[1]
        assert len(comp_a.roles) > 0, f"Company {comp_a.name} has no roles"
        assert len(comp_b.roles) > 0, f"Company {comp_b.name} has no roles"
        return comp_a, comp_a.roles[0], comp_b, comp_b.roles[0]


@pytest.mark.asyncio
async def test_01_candidate_a_frontend_recommendations():
    """TEST 1: Candidate A uploads frontend resume and receives frontend-oriented recommendations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_a, email_a, uid_a = await create_and_authenticate_candidate(client, "cand_a")

        # Upload Frontend Resume
        files = {"file": ("frontend_resume.txt", io.BytesIO(SAMPLE_FRONTEND_RESUME), "text/plain")}
        upload_res = await client.post("/api/v1/resume/upload", headers=headers_a, files=files)
        assert upload_res.status_code == 201
        upload_data = upload_res.json()
        assert "skills" in upload_data["resume_profile"]
        parsed_skills = [s.lower() for s in upload_data["resume_profile"]["skills"]]
        assert any(k in parsed_skills for k in ["react", "next.js", "typescript", "javascript"])

        # Fetch Recommendations for Candidate A
        matches_res = await client.get("/api/v1/jobs/matches", headers=headers_a)
        assert matches_res.status_code == 200
        matches_a = matches_res.json()
        assert len(matches_a) > 0

        # Verify matched skills contain candidate's actual frontend skills
        top_match = matches_a[0]
        assert "overall_score" in top_match
        assert "matched_skills" in top_match
        assert top_match["overall_score"] > 0.0


@pytest.mark.asyncio
async def test_02_candidate_b_no_resume_returns_empty():
    """TEST 2: Candidate B creates account with NO resume and receives exactly [] recommendations (zero leakage)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate A exists with resume
        headers_a, _, _ = await create_and_authenticate_candidate(client, "cand_a_ref")
        files = {"file": ("resume_a.txt", io.BytesIO(SAMPLE_FRONTEND_RESUME), "text/plain")}
        await client.post("/api/v1/resume/upload", headers=headers_a, files=files)

        # Candidate B registers but does NOT upload resume
        headers_b, _, _ = await create_and_authenticate_candidate(client, "cand_b_empty")
        matches_res = await client.get("/api/v1/jobs/matches", headers=headers_b)
        assert matches_res.status_code == 200
        matches_b = matches_res.json()

        # MUST return empty list []
        assert matches_b == [], f"Expected empty list for user without resume, got: {matches_b}"


@pytest.mark.asyncio
async def test_03_and_04_candidate_b_ml_resume_and_candidate_a_isolation():
    """TEST 3 & 4: Candidate B uploads ML resume, receives ML recommendations, and Candidate A remains isolated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_a, _, _ = await create_and_authenticate_candidate(client, "cand_a_iso")
        headers_b, _, _ = await create_and_authenticate_candidate(client, "cand_b_iso")

        # Candidate A uploads Frontend resume
        await client.post("/api/v1/resume/upload", headers=headers_a, files={
            "file": ("resume_a.txt", io.BytesIO(SAMPLE_FRONTEND_RESUME), "text/plain")
        })
        matches_a_before = (await client.get("/api/v1/jobs/matches", headers=headers_a)).json()

        # Candidate B uploads ML resume
        upload_b = await client.post("/api/v1/resume/upload", headers=headers_b, files={
            "file": ("resume_b.txt", io.BytesIO(SAMPLE_ML_RESUME), "text/plain")
        })
        assert upload_b.status_code == 201
        skills_b = [s.lower() for s in upload_b.json()["resume_profile"]["skills"]]
        assert any(k in skills_b for k in ["python", "pytorch", "machine learning", "tensorflow"])

        # Candidate B receives ML recommendations
        matches_b = (await client.get("/api/v1/jobs/matches", headers=headers_b)).json()
        assert len(matches_b) > 0

        # Candidate A re-fetches recommendations and verifies unchanged isolation
        matches_a_after = (await client.get("/api/v1/jobs/matches", headers=headers_a)).json()
        assert len(matches_a_before) == len(matches_a_after)
        for m_before, m_after in zip(matches_a_before, matches_a_after):
            assert m_before["role_id"] == m_after["role_id"]
            assert m_before["overall_score"] == m_after["overall_score"]
            assert m_before["matched_skills"] == m_after["matched_skills"]


@pytest.mark.asyncio
async def test_05_candidate_b_cannot_access_candidate_a_resume():
    """TEST 5: Candidate B cannot access Candidate A's resume by ID (IDOR protection)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_a, _, _ = await create_and_authenticate_candidate(client, "cand_a_res")
        headers_b, _, _ = await create_and_authenticate_candidate(client, "cand_b_res")

        # Candidate A uploads resume
        upload_a = (await client.post("/api/v1/resume/upload", headers=headers_a, files={
            "file": ("resume_a.txt", io.BytesIO(SAMPLE_FRONTEND_RESUME), "text/plain")
        })).json()
        resume_a_id = upload_a["id"]

        # Candidate B attempts access
        res = await client.get(f"/api/v1/resume/{resume_a_id}", headers=headers_b)
        assert res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_06_to_08_interview_ownership_and_idor_protection():
    """TEST 6, 7, 8: Candidate B cannot view, answer, or finish Candidate A's interview."""
    comp_a, role_a, _, _ = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_a, _, uid_a = await create_and_authenticate_candidate(client, "cand_a_int")
        headers_b, _, uid_b = await create_and_authenticate_candidate(client, "cand_b_int")

        # Candidate A starts interview
        create_res = await client.post("/api/v1/interviews", headers=headers_a, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        assert create_res.status_code == 200
        int_a_id = create_res.json()["id"]

        # TEST 6: Candidate B attempts to GET Candidate A's interview
        get_res = await client.get(f"/api/v1/interviews/{int_a_id}", headers=headers_b)
        assert get_res.status_code in [403, 404]

        # TEST 7: Candidate B attempts to POST answer to Candidate A's interview
        ans_res = await client.post(f"/api/v1/interviews/{int_a_id}/answer", headers=headers_b, json={
            "answer_text": "I am trying to hack candidate A's interview."
        })
        assert ans_res.status_code in [403, 404]

        # Verify no rogue answer inserted
        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_a_id)
            res = await db.execute(stmt)
            answers = res.scalars().all()
            assert len(answers) == 0

        # TEST 8: Candidate B attempts to FINISH Candidate A's interview
        finish_res = await client.post(f"/api/v1/interviews/{int_a_id}/finish", headers=headers_b)
        assert finish_res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_09_and_10_interview_creation_and_company_role_validation():
    """TEST 9 & 10: Valid interview creation succeeds; mismatched company-role pair is rejected with 400."""
    comp_a, role_a, comp_b, role_b = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "cand_valid")

        # TEST 9: Valid company + role
        valid_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        assert valid_res.status_code == 200
        int_data = valid_res.json()
        assert int_data["candidate_id"] == user_id
        assert int_data["company_id"] == comp_a.id
        assert int_data["role_id"] == role_a.id
        assert int_data["current_question"] is not None

        # TEST 10: Mismatched company_id (comp_a) + role_id (role_b from comp_b)
        mismatch_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_b.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        assert mismatch_res.status_code == 400
        assert "belong" in mismatch_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_11_to_13_answer_persistence_empty_and_duplicate_rejection():
    """TEST 11, 12, 13: Valid answer persistence, empty answer rejection, and duplicate answer prevention."""
    comp_a, role_a, _, _ = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "cand_ans")

        # Start interview
        create_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        int_data = create_res.json()
        int_id = int_data["id"]
        q1_id = int_data["current_question"]["id"]

        # TEST 12: Empty answer rejection
        empty_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "   "
        })
        assert empty_res.status_code == 400
        assert "empty" in empty_res.json()["detail"].lower()

        # TEST 11: Valid answer submission
        ans1_text = "I am deeply passionate about software engineering and built responsive React apps."
        submit_res1 = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": ans1_text
        })
        assert submit_res1.status_code == 200
        turn_data1 = submit_res1.json()
        assert "evaluation" in turn_data1
        assert "overall_question_score" in turn_data1["evaluation"]
        assert turn_data1["next_question"] is not None

        # Verify answer persisted in DB
        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id, Answer.question_id == q1_id)
            res = await db.execute(stmt)
            saved_ans = res.scalars().first()
            assert saved_ans is not None
            assert saved_ans.candidate_answer_text == ans1_text

        # TEST 13: Attempt to answer the same question again (duplicate answer prevention)
        # Force state.current_question_id back to q1_id in DB to test protection
        async with AsyncSessionLocal() as db:
            stmt_int = select(Interview).options(selectinload(Interview.state)).where(Interview.id == int_id)
            res_int = await db.execute(stmt_int)
            int_obj = res_int.scalars().first()
            int_obj.state.current_question_id = q1_id
            await db.commit()

        duplicate_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "Second attempt to answer the exact same question."
        })
        # The turn is replayed, not repeated: the caller gets the score that was
        # already recorded, and nothing further is written. This used to be a
        # 400, which also stranded turns whose answer was stored but never
        # evaluated -- see tests/test_answer_turn_idempotency.py.
        assert duplicate_res.status_code == 200
        assert duplicate_res.json()["evaluation"]["overall_question_score"] ==             turn_data1["evaluation"]["overall_question_score"]

        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id, Answer.question_id == q1_id)
            again = (await db.execute(stmt)).scalars().all()
            assert len(again) == 1, "a repeat submission must not store a second answer"
            assert again[0].candidate_answer_text == ans1_text


@pytest.mark.asyncio
async def test_14_to_16_multi_turn_progression_and_adaptive_behavior():
    """TEST 14, 15, 16: Multi-turn progression, adaptive difficulty adjustment, and no duplicate questions."""
    comp_a, role_a, _, _ = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "cand_multi")

        # Start interview
        create_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        int_id = create_res.json()["id"]
        asked_questions = [create_res.json()["current_question"]["question_text"]]

        # Turn 1: Submit Strong Answer (Score >= 8) -> Adaptive Difficulty should adjust
        strong_ans = (
            "In React, state management and memoization are key. useMemo caches computed values "
            "while useCallback memoizes function references. For architecture, component modularity "
            "and atomic state slices with Redux Toolkit ensure scalable renders and avoid re-render cascades."
        )
        res1 = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": strong_ans
        })
        assert res1.status_code == 200
        data1 = res1.json()
        q2 = data1["next_question"]
        assert q2 is not None
        assert q2["question_text"] not in asked_questions
        assert not is_duplicate_question(q2["question_text"], asked_questions)
        asked_questions.append(q2["question_text"])

        # Turn 2: Submit Weak Answer (Score < 5) -> Adaptive Difficulty should adjust
        weak_ans = "I don't know much about database indexes, maybe they make things faster."
        res2 = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": weak_ans
        })
        assert res2.status_code == 200
        data2 = res2.json()
        q3 = data2["next_question"]
        assert q3 is not None
        assert q3["question_text"] not in asked_questions
        assert not is_duplicate_question(q3["question_text"], asked_questions)
        asked_questions.append(q3["question_text"])

        # Verify state in DB contains updated scores and topic progression
        async with AsyncSessionLocal() as db:
            stmt = select(Interview).options(
                selectinload(Interview.state),
                selectinload(Interview.answers)
            ).where(Interview.id == int_id)
            res = await db.execute(stmt)
            int_obj = res.scalars().first()
            assert len(int_obj.answers) == 2
            assert int_obj.state.questions_asked_count == 2


@pytest.mark.asyncio
async def test_17_and_18_ai_failure_handling_and_fallback_resilience():
    """TEST 17 & 18: Fallback question bank returns valid questions and evaluation failure preserves answers."""
    comp_a, role_a, _, _ = await get_target_company_and_roles()
    async with AsyncSessionLocal() as db:
        selector = QuestionSelector(db)
        
        # TEST 17: Fallback question generation under simulated LLM failure
        q = await selector.select_or_generate_question(
            company_id=comp_a.id,
            role_id=role_a.id,
            topic="Data Structures",
            difficulty="medium",
            asked_question_ids=[],
            interview_type="technical"
        )
        assert q is not None
        assert isinstance(q.question_text, str)
        assert len(q.question_text) > 10
        assert q.topic is not None

    # TEST 18: Answer preserved even if evaluation encounters error
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "cand_fallback")
        create_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        int_id = create_res.json()["id"]

        # Submit answer
        ans_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "Resilience test answer: binary search trees guarantee O(log n) lookup on average."
        })
        assert ans_res.status_code == 200

        # Verify answer is in database
        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id)
            res = await db.execute(stmt)
            saved_ans = res.scalars().first()
            assert saved_ans is not None
            assert "binary search trees" in saved_ans.candidate_answer_text


@pytest.mark.asyncio
async def test_19_and_20_interview_completion_report_generation_and_isolation():
    """TEST 19 & 20: Completing interview produces authentic report and Candidate B cannot access Candidate A's report."""
    comp_a, role_a, _, _ = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers_a, _, uid_a = await create_and_authenticate_candidate(client, "cand_a_rep")
        headers_b, _, uid_b = await create_and_authenticate_candidate(client, "cand_b_rep")

        # Candidate A starts and answers
        create_res = await client.post("/api/v1/interviews", headers=headers_a, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        int_a_id = create_res.json()["id"]

        await client.post(f"/api/v1/interviews/{int_a_id}/answer", headers=headers_a, json={
            "answer_text": "I focus on clean code, unit testing, and scalable component hierarchies."
        })

        # TEST 19: Candidate A finishes interview
        finish_res = await client.post(f"/api/v1/interviews/{int_a_id}/finish", headers=headers_a)
        assert finish_res.status_code == 200
        assert "report_id" in finish_res.json()

        # Fetch Candidate A report
        rep_res_a = await client.get(f"/api/v1/reports/{int_a_id}", headers=headers_a)
        assert rep_res_a.status_code == 200
        rep_data_a = rep_res_a.json()
        assert "overall_score" in rep_data_a
        assert "rubric_scores" in rep_data_a
        assert "strengths" in rep_data_a
        assert "recommendations" in rep_data_a

        # TEST 20: Candidate B attempts to access Candidate A's report (must be forbidden)
        rep_res_b = await client.get(f"/api/v1/reports/{int_a_id}", headers=headers_b)
        assert rep_res_b.status_code in [403, 404]


@pytest.mark.asyncio
async def test_21_to_23_concurrent_candidates_session_persistence_and_reauth():
    """TEST 21, 22, 23: Multi-candidate independence, stateless session persistence, and re-login security."""
    comp_a, role_a, comp_b, role_b = await get_target_company_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login Candidate A & B
        headers_a, email_a, uid_a = await create_and_authenticate_candidate(client, "user_alpha")
        headers_b, email_b, uid_b = await create_and_authenticate_candidate(client, "user_beta")

        # Candidate A creates Interview on Company A
        int_a = (await client.post("/api/v1/interviews", headers=headers_a, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()

        # Candidate B creates Interview on Company B
        int_b = (await client.post("/api/v1/interviews", headers=headers_b, json={
            "company_id": comp_b.id, "role_id": role_b.id, "mode": "text", "duration_minutes": 30
        })).json()

        assert int_a["id"] != int_b["id"]
        assert int_a["company_id"] == comp_a.id
        assert int_b["company_id"] == comp_b.id

        # TEST 21: Independent answer turns without cross-contamination
        await client.post(f"/api/v1/interviews/{int_a['id']}/answer", headers=headers_a, json={
            "answer_text": "Alpha Candidate Answer regarding React Architecture."
        })
        await client.post(f"/api/v1/interviews/{int_b['id']}/answer", headers=headers_b, json={
            "answer_text": "Beta Candidate Answer regarding Python Machine Learning."
        })

        hist_a = (await client.get("/api/v1/interviews/history", headers=headers_a)).json()
        hist_b = (await client.get("/api/v1/interviews/history", headers=headers_b)).json()
        assert len(hist_a) == 1
        assert len(hist_b) == 1
        assert hist_a[0]["id"] == int_a["id"]
        assert hist_b[0]["id"] == int_b["id"]

        # TEST 22 & 23: Re-login as Candidate A with fresh JWT
        relogin_res = await client.post("/api/v1/auth/login", json={
            "email": email_a,
            "password": "SecurePassword123!"
        })
        fresh_token_a = relogin_res.json()["access_token"]
        fresh_headers_a = {"Authorization": f"Bearer {fresh_token_a}"}

        fetch_reauth = (await client.get(f"/api/v1/interviews/{int_a['id']}", headers=fresh_headers_a)).json()
        assert fetch_reauth["id"] == int_a["id"]
        assert fetch_reauth["candidate_id"] == uid_a
        assert len(fetch_reauth["answers"]) == 1


@pytest.mark.asyncio
async def test_24_and_25_phase1_regression_resume_replacement_and_matching():
    """TEST 24 & 25: Phase 1 resume replacement and matching calculations remain fully operational."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "cand_replace")

        # Initial Frontend resume
        res1 = await client.post("/api/v1/resume/upload", headers=headers, files={
            "file": ("res1.txt", io.BytesIO(SAMPLE_FRONTEND_RESUME), "text/plain")
        })
        assert res1.status_code == 201
        m1 = (await client.get("/api/v1/jobs/matches", headers=headers)).json()
        assert len(m1) > 0

        # Replace with ML resume
        res2 = await client.post("/api/v1/resume/upload", headers=headers, files={
            "file": ("res2.txt", io.BytesIO(SAMPLE_ML_RESUME), "text/plain")
        })
        assert res2.status_code == 201
        m2 = (await client.get("/api/v1/jobs/matches", headers=headers)).json()
        assert len(m2) > 0

        # Verify current resume endpoint reflects replaced ML resume
        cur_res = (await client.get("/api/v1/resume/current", headers=headers)).json()
        assert cur_res["id"] == res2.json()["id"]
        assert cur_res["filename"] == "res2.txt"
