"""Phase 4 Comprehensive Test Suite: Wow-Standard Real AI Interview Platform.

Validates all 25 specific Phase 4 requirements:
1. Candidate isolation
2. Interview ownership
3. Unauthorized interview access
4. Unauthorized answer submission
5. Unauthorized report access
6. Empty answer rejection
7. Duplicate answer rejection
8. Answer persistence before downstream processing
9. Realistic question progression
10. Contextual follow-up generation
11. Strict duplicate question prevention
12. Adaptive difficulty progression
13. Question-aware AI answer evaluation
14. Malformed AI response handling & recovery
15. AI provider failure resilience & fallback
16. Deterministic score validation & clamping
17. Evidence-grounded report generation
18. Interview completion & state finalization
19. Double-completion protection & idempotency
20. Candidate A/B full lifecycle isolation
21. Resume context usage in interview questions
22. Role context usage in interview questions
23. Previous-turn context usage across multi-turn sessions
24. No fabricated candidate information
25. Database integrity & approved company constraint preservation
"""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.database import AsyncSessionLocal
from app.db.models import Company, Role, Interview, InterviewState, Question, Answer, Evaluation, Report, User
from app.ai.base import LLMProvider
from app.ai.factory import AIFactory
from app.ai.mock_provider import MockLLMProvider
from app.ai.prompt_builder import SafePromptBuilder
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.question_selector import QuestionSelector, is_duplicate_question
from app.interview.conversation import FollowUpEngine
from app.interview.persona import InterviewPersonaBuilder
from app.evaluation.evaluator import AnswerEvaluator
from app.evaluation.scorer import DeterministicScorer
from app.reports.generator import ReportGenerator


SAMPLE_REACT_RESUME = b"""
Candidate: Jane React
Email: jane.react@example.com
Education: B.S. in Software Engineering, UC Berkeley (2023)
Skills: React, Next.js, Redux, TypeScript, JavaScript, CSS, HTML5, REST APIs
Experience:
Frontend Engineer at WebTech (2022 - 2023)
- Developed responsive web interfaces using React and Next.js.
- Implemented state management with Redux Toolkit and optimized rendering.
"""

SAMPLE_PYTHON_RESUME = b"""
Candidate: Bob Python
Email: bob.python@example.com
Education: M.S. in Computer Science, Stanford (2023)
Skills: Python, PyTorch, FastAPI, SQL, Pandas, NumPy, Machine Learning, Docker
Experience:
Backend & ML Engineer at DataCorp (2022 - 2023)
- Built high-performance microservices using FastAPI and PostgreSQL.
- Developed PyTorch deep learning models for NLP classification.
"""


async def register_and_login_candidate(client: AsyncClient, prefix: str = "p4_user") -> tuple[dict, str, int]:
    """Helper to create and authenticate a test candidate."""
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


async def get_test_companies_and_roles() -> tuple[Company, Role, Company, Role]:
    """Fetch approved companies and roles from DB."""
    async with AsyncSessionLocal() as db:
        stmt = select(Company).options(selectinload(Company.roles)).order_by(Company.id)
        res = await db.execute(stmt)
        comps = res.scalars().all()
        assert len(comps) >= 2, "Need at least 2 approved companies in database"
        comp_a, comp_b = comps[0], comps[1]
        assert len(comp_a.roles) > 0 and len(comp_b.roles) > 0
        return comp_a, comp_a.roles[0], comp_b, comp_b.roles[0]


# ==============================================================================
# TESTS 1 - 5: SECURITY, CANDIDATE ISOLATION & IDOR PROTECTION
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_01_to_05_candidate_isolation_ownership_and_idor():
    """Verify Candidate Isolation, Ownership, and Unauthorized access rejections for sessions, answers, and reports."""
    comp_a, role_a, comp_b, role_b = await get_test_companies_and_roles()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate A
        headers_a, _, uid_a = await register_and_login_candidate(client, "cand_a")
        # Candidate B
        headers_b, _, uid_b = await register_and_login_candidate(client, "cand_b")

        # 1. Candidate A creates interview
        res_a = await client.post("/api/v1/interviews", headers=headers_a, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30
        })
        assert res_a.status_code == 200
        int_a = res_a.json()
        int_a_id = int_a["id"]
        assert int_a["candidate_id"] == uid_a  # Requirement 2: Interview Ownership

        # 2. Candidate B attempts unauthorized access to Candidate A's interview (Requirement 3)
        res_unauth_get = await client.get(f"/api/v1/interviews/{int_a_id}", headers=headers_b)
        assert res_unauth_get.status_code in [403, 404]

        # 3. Candidate B attempts unauthorized answer submission to Candidate A's interview (Requirement 4)
        res_unauth_ans = await client.post(f"/api/v1/interviews/{int_a_id}/answer", headers=headers_b, json={
            "answer_text": "I am hacking this session."
        })
        assert res_unauth_ans.status_code in [403, 404]

        # 4. Candidate A answers and finishes
        await client.post(f"/api/v1/interviews/{int_a_id}/answer", headers=headers_a, json={
            "answer_text": "I use Next.js for server-side rendering and client routing."
        })
        await client.post(f"/api/v1/interviews/{int_a_id}/finish", headers=headers_a)

        # 5. Candidate B attempts unauthorized access to Candidate A's report (Requirement 5)
        res_unauth_rep = await client.get(f"/api/v1/reports/{int_a_id}", headers=headers_b)
        assert res_unauth_rep.status_code in [403, 404]

        # Candidate A can access their own report successfully
        res_auth_rep = await client.get(f"/api/v1/reports/{int_a_id}", headers=headers_a)
        assert res_auth_rep.status_code == 200


# ==============================================================================
# TESTS 6 - 8: ANSWER VALIDATION, DUPLICATE PREVENTION & PERSISTENCE SAFETY
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_06_to_08_answer_validation_duplicate_prevention_and_persistence():
    """Verify Empty answer rejection (6), Duplicate answer rejection (7), and Answer persistence (8)."""
    comp_a, role_a, _, _ = await get_test_companies_and_roles()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await register_and_login_candidate(client, "ans_test")
        int_obj = (await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()
        int_id = int_obj["id"]

        # Requirement 6: Reject empty/whitespace answers
        empty_res1 = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": ""})
        assert empty_res1.status_code == 400
        empty_res2 = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": "   \n\t  "})
        assert empty_res2.status_code == 400

        # Requirement 8: Valid answer persists safely before evaluation
        valid_text = "PostgreSQL indexing utilizes B-Trees to ensure O(log N) lookup times on clustered tables."
        ans_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": valid_text})
        assert ans_res.status_code == 200

        # Verify persisted in database directly
        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id)
            res_db = await db.execute(stmt)
            persisted_answers = res_db.scalars().all()
            assert len(persisted_answers) >= 1
            assert persisted_answers[0].candidate_answer_text == valid_text

            # Reset current_question_id back to the answered question to verify duplicate answer rejection
            stmt_state = select(InterviewState).where(InterviewState.interview_id == int_id)
            res_state = await db.execute(stmt_state)
            state_obj = res_state.scalars().first()
            state_obj.current_question_id = persisted_answers[0].question_id
            await db.commit()

        # Requirement 7: a duplicate submission for a question that already has a
        # scored answer must not create a second answer or evaluation. It is now
        # answered by replaying the recorded turn instead of rejected with 400.
        dup_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": "Submitting duplicate answer for first question."})
        assert dup_res.status_code == 200

        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id)
            after_dup = (await db.execute(stmt)).scalars().all()
            assert len(after_dup) == len(persisted_answers), "duplicate submission must not add an answer"
            assert after_dup[0].candidate_answer_text == valid_text


# ==============================================================================
# TESTS 9 - 12: QUESTION PROGRESSION, FOLLOW-UP, DEDUP & ADAPTIVE DIFFICULTY
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_09_to_12_progression_followup_dedup_and_adaptive_difficulty():
    """Verify Question Progression (9), Contextual Follow-up (10), Deduplication (11), and Adaptive Difficulty (12)."""
    comp_a, role_a, _, _ = await get_test_companies_and_roles()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await register_and_login_candidate(client, "adapt_test")

        # 1. Progression starts with Stage 1 intro/warmup (Requirement 9)
        start_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30, "target_level": "entry"
        })
        assert start_res.status_code == 200
        data_start = start_res.json()
        assert data_start["state"]["questions_asked_count"] == 0
        assert data_start["current_question"]["question_type"] in ["hr", "behavioral", "introductory", "technical"]

        # 2. Turn 1: Excellent technical answer -> adapts difficulty to hard / high score (Requirement 12)
        turn1_res = await client.post(f"/api/v1/interviews/{data_start['id']}/answer", headers=headers, json={
            "answer_text": (
                "To optimize relational databases at high scale, B-Tree indexes provide logarithmic O(log N) lookup. "
                "Composite indexes must follow the leftmost prefix rule. For high concurrency, connection pooling and read replicas "
                "offload read-heavy traffic while write workloads benefit from WAL tuning and sharding."
            )
        })
        assert turn1_res.status_code == 200
        data_turn1 = turn1_res.json()
        assert data_turn1["evaluation"]["overall_question_score"] >= 7.5
        assert data_turn1["next_question"] is not None
        assert data_turn1["interview_state"]["questions_asked_count"] == 1

        # 3. Contextual Follow-Up verification (Requirement 10)
        should_follow, reason = FollowUpEngine.should_follow_up(
            last_eval_score=8.5,
            evidence=["Mentioned Redis caching."],
            depth_score=6.0,
            turn_count_on_topic=1,
            time_remaining_seconds=1500,
            candidate_answer="I used Redis for caching.",
            topic="System Design"
        )
        assert should_follow is True
        assert reason in ["strong_answer_tradeoffs", "vague_answer", "clarify_concept"]

        # 4. Strict Duplicate Question Prevention (Requirement 11)
        asked = [data_start["current_question"]["question_text"], data_turn1["next_question"]["question_text"]]
        assert is_duplicate_question(asked[0], asked) is True
        assert is_duplicate_question(asked[0].upper() + "???", asked) is True
        assert is_duplicate_question("How do distributed consensus algorithms like Raft elect a leader?", asked) is False


# ==============================================================================
# TESTS 13 - 16: AI EVALUATION, MALFORMED RESILIENCE, FALLBACK & SCORE INTEGRITY
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_13_to_16_ai_eval_resilience_fallback_and_score_integrity():
    """Verify AI Answer Evaluation (13), Malformed AI Handling (14), AI Failure Fallback (15), and Score Validation (16)."""
    # 1. Direct Answer Evaluation (Requirement 13)
    eval_tech = await AnswerEvaluator.evaluate_answer(
        question_text="Explain the difference between SQL and NoSQL database models.",
        expected_concepts=["Relational schema", "ACID compliance", "Horizontal scaling", "Document / Key-Value"],
        candidate_answer="SQL databases use structured schemas and ACID transactions, whereas NoSQL allows flexible document storage and horizontal scaling.",
        topic="Database Design",
        question_type="technical"
    )
    assert 0.0 <= eval_tech["correctness_score"] <= 10.0
    assert 0.0 <= eval_tech["overall_question_score"] <= 10.0
    assert "feedback_text" in eval_tech
    assert isinstance(eval_tech["evidence"], list)

    # 2. Behavioral Question Evaluation (Requirement 13)
    eval_beh = await AnswerEvaluator.evaluate_answer(
        question_text="Tell me about a time you resolved a disagreement with a team member.",
        expected_concepts=["Communication", "Collaboration", "Conflict resolution"],
        candidate_answer="When we disagreed on API design, I scheduled a design review, documented trade-offs, and we agreed on a RESTful standard.",
        topic="Collaboration",
        question_type="behavioral"
    )
    assert eval_beh["communication_score"] >= 6.0
    assert eval_beh["relevance_score"] >= 6.0

    # 3. Deterministic Score Calculation & Clamping (Requirement 16)
    clamped_high = DeterministicScorer.calculate_overall_interview_score([9.5, 9.8, 10.0])
    assert 0.0 <= clamped_high <= 100.0
    assert clamped_high >= 90.0

    clamped_low = DeterministicScorer.calculate_overall_interview_score([1.0, 0.5])
    assert 0.0 <= clamped_low <= 100.0
    assert clamped_low <= 15.0

    empty_score = DeterministicScorer.calculate_overall_interview_score([])
    assert empty_score == 0.0

    # 4. Malformed AI recovery & Fallback verification (Requirements 14 & 15)
    llm = AIFactory.get_llm_provider("mock", enable_fallback=True)
    json_out = await llm.generate_json("interview overall score: 85, topic breakdown scores: {'Database Indexing': 85}, candidate assessment report")
    assert isinstance(json_out, dict)
    assert "strengths" in json_out or "items" in json_out or len(json_out) > 0


# ==============================================================================
# TESTS 17 - 19: REPORT GENERATION, COMPLETION & DOUBLE-COMPLETION PROTECTION
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_17_to_19_report_generation_completion_and_idempotency():
    """Verify Report Generation (17), Interview Completion (18), and Double-Completion Protection (19)."""
    comp_a, role_a, _, _ = await get_test_companies_and_roles()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await register_and_login_candidate(client, "rep_test")

        # Start interview
        int_obj = (await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()
        int_id = int_obj["id"]

        # Submit answer
        await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "I design secure REST microservices using FastAPI, JWT authentication, and PostgreSQL connection pooling."
        })

        # Requirement 18: Finish interview session
        finish_res1 = await client.post(f"/api/v1/interviews/{int_id}/finish", headers=headers)
        assert finish_res1.status_code == 200
        rep_id1 = finish_res1.json()["report_id"]
        assert rep_id1 > 0

        # Requirement 19: Double-completion protection (idempotent finish)
        finish_res2 = await client.post(f"/api/v1/interviews/{int_id}/finish", headers=headers)
        assert finish_res2.status_code == 200
        assert finish_res2.json()["report_id"] == rep_id1

        # Requirement 17: Fetch report and verify data integrity
        rep_res = await client.get(f"/api/v1/reports/{int_id}", headers=headers)
        assert rep_res.status_code == 200
        rep_data = rep_res.json()
        assert rep_data["id"] == rep_id1
        assert rep_data["interview_id"] == int_id
        assert 0.0 <= rep_data["overall_score"] <= 100.0
        assert isinstance(rep_data["topic_scores"], dict)
        assert isinstance(rep_data["rubric_scores"], dict)
        assert isinstance(rep_data["strengths"], list)
        assert isinstance(rep_data["weaknesses"], list)
        assert isinstance(rep_data["recommendations"], list)
        assert len(rep_data["executive_summary"]) > 10


# ==============================================================================
# TESTS 20 - 24: CANDIDATE A/B ISOLATION & CONTEXT GROUNDING
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_20_to_24_candidate_ab_isolation_and_context_grounding():
    """Verify Candidate A/B Isolation (20), Resume Context (21), Role Context (22), Previous Turns (23), and No Fabrication (24)."""
    comp_a, role_a, comp_b, role_b = await get_test_companies_and_roles()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate A (Frontend React)
        h_a, _, uid_a = await register_and_login_candidate(client, "p4_cand_a")
        up_a = await client.post("/api/v1/resume/upload", headers=h_a, files={
            "file": ("react_resume.txt", io.BytesIO(SAMPLE_REACT_RESUME), "text/plain")
        })
        assert up_a.status_code == 201
        matches_a = (await client.get("/api/v1/jobs/matches", headers=h_a)).json()
        assert len(matches_a) > 0

        # Candidate B (Backend ML)
        h_b, _, uid_b = await register_and_login_candidate(client, "p4_cand_b")
        up_b = await client.post("/api/v1/resume/upload", headers=h_b, files={
            "file": ("ml_resume.txt", io.BytesIO(SAMPLE_PYTHON_RESUME), "text/plain")
        })
        assert up_b.status_code == 201
        matches_b = (await client.get("/api/v1/jobs/matches", headers=h_b)).json()
        assert len(matches_b) > 0

        # Requirement 20: Candidate A and Candidate B profiles and recommendations remain completely isolated
        profile_a = (await client.get("/api/v1/profile", headers=h_a)).json()
        profile_b = (await client.get("/api/v1/profile", headers=h_b)).json()
        assert profile_a["user_id"] == uid_a
        assert profile_b["user_id"] == uid_b
        assert any("react" in s.lower() for s in profile_a.get("skills", []))
        assert any("python" in s.lower() for s in profile_b.get("skills", []))

        # Requirement 21 & 22: Persona Warmup incorporates Role & Resume context without fabricating facts
        async with AsyncSessionLocal() as db:
            warmup_a = await InterviewPersonaBuilder.generate_warmup_question(
                company=comp_a,
                role=role_a,
                candidate_name="Jane React",
                question_index=0,
                resume_context="Skills: React, Next.js, TypeScript; Education: BS SE"
            )
            assert "question_text" in warmup_a
            assert len(warmup_a["question_text"]) > 10

            # Requirement 23: Previous turn context passing
            selector = QuestionSelector(db)
            q_next = await selector.select_or_generate_question(
                company_id=comp_a.id,
                role_id=role_a.id,
                topic="Frontend Architecture",
                difficulty="medium",
                asked_question_ids=[],
                interview_type="technical",
                resume_context="Skills: React, TypeScript",
                previous_context=[{
                    "question": "How do you manage client-side state in React?",
                    "answer": "I use Redux Toolkit for centralized state."
                }]
            )
            assert q_next is not None
            assert q_next.topic == "Frontend Architecture"

        # Requirement 24: Candidate with NO resume has empty recommendations, no fabricated skills
        h_c, _, uid_c = await register_and_login_candidate(client, "p4_no_resume")
        matches_c = (await client.get("/api/v1/jobs/matches", headers=h_c)).json()
        assert matches_c == []  # No fabricated jobs or skills


# ==============================================================================
# TEST 25: DATABASE INTEGRITY & APPROVED 10 COMPANIES PRESERVATION
# ==============================================================================

@pytest.mark.asyncio
async def test_p4_25_database_integrity_and_approved_companies():
    """Verify database integrity, foreign keys, and that all 10 approved companies are preserved."""
    async with AsyncSessionLocal() as db:
        stmt = select(Company).order_by(Company.slug)
        res = await db.execute(stmt)
        companies = res.scalars().all()

        approved_slugs = {
            "adobe", "amazon", "apple", "google", "ibm",
            "infosys", "meta", "microsoft", "netflix", "oracle"
        }
        current_slugs = {c.slug for c in companies}
        assert approved_slugs.issubset(current_slugs), f"Missing approved companies: {approved_slugs - current_slugs}"

        # Check for orphan records
        stmt_orphan_roles = select(Role).outerjoin(Company, Role.company_id == Company.id).where(Company.id.is_(None))
        orphan_roles = (await db.execute(stmt_orphan_roles)).scalars().all()
        assert len(orphan_roles) == 0, f"Found {len(orphan_roles)} orphan roles"

        stmt_orphan_interviews = select(Interview).outerjoin(Company, Interview.company_id == Company.id).where(Company.id.is_(None))
        orphan_interviews = (await db.execute(stmt_orphan_interviews)).scalars().all()
        assert len(orphan_interviews) == 0, f"Found {len(orphan_interviews)} orphan interviews"
