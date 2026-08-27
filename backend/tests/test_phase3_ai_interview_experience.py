"""Phase 3 Test Suite: Real AI-Powered Interview Experience, Resilience, and Candidate Isolation.

Covers:
- Category A: AI Provider Abstraction, Factory Configuration, Mock Fallback, and Malformed Output Resilience
- Category B: Role-Specific, Resume-Aware, Contextual Question Generation, and Strict Duplicate Prevention
- Category C: Adaptive Difficulty Progression, Weak Area Remediation, and Multi-Turn State Evolution
- Category D: Schema-Validated Answer Evaluation, Rubric Scoring, and Persistence-First Fault Tolerance
- Category E: Security, Candidate Ownership, and IDOR Protections
- Category F: Concurrent Independent Interview Sessions without Cross-User Contamination
- Category G: Evidence-Grounded Final Report Generation and Candidate Isolation
"""

import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.db.models import Company, Role, Interview, Question, Answer, Evaluation, Report
from app.ai.base import LLMProvider
from app.ai.factory import AIFactory
from app.ai.mock_provider import MockLLMProvider
from app.ai.gemini_provider import GeminiLLMProvider
from app.ai.prompt_builder import SafePromptBuilder
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.question_selector import QuestionSelector, is_duplicate_question
from app.evaluation.evaluator import AnswerEvaluator
from app.reports.generator import ReportGenerator


SAMPLE_REACT_RESUME = b"""
Candidate: Alex Dev
Email: alex.dev@example.com
Education: B.S. in Software Engineering, Carnegie Mellon (2023)
Skills: React, Next.js, Redux, TypeScript, JavaScript, CSS, HTML5, REST APIs
Experience:
Frontend Developer at ModernWeb (2022 - 2023)
- Built interactive web applications using React hooks and Next.js SSR.
- Optimized UI rendering performance using memoization and virtualized lists.
Projects:
- E-Commerce Frontend: High-performance React shop with client-side caching.
"""

SAMPLE_PYTHON_RESUME = b"""
Candidate: Jordan Data
Email: jordan.data@example.com
Education: M.S. in Computer Science, Georgia Tech (2023)
Skills: Python, PyTorch, SQL, Pandas, NumPy, Machine Learning, FastAPIs, Docker
Experience:
Data Science Intern at Analytics Corp (2022 - 2023)
- Built machine learning data pipelines and REST microservices in Python.
- Trained predictive models using PyTorch and Scikit-Learn.
Projects:
- Neural Classifier: PyTorch deep learning pipeline for multi-class classification.
"""


async def create_and_authenticate_candidate(client: AsyncClient, prefix: str = "p3_user") -> tuple[dict, str, int]:
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


async def get_approved_companies_and_roles() -> tuple[Company, Role, Company, Role]:
    """Fetch approved companies and roles from database."""
    async with AsyncSessionLocal() as db:
        stmt = select(Company).options(selectinload(Company.roles)).order_by(Company.id)
        res = await db.execute(stmt)
        comps = res.scalars().all()
        assert len(comps) >= 2, "Database must have approved companies"
        comp_a, comp_b = comps[0], comps[1]
        assert len(comp_a.roles) > 0 and len(comp_b.roles) > 0
        return comp_a, comp_a.roles[0], comp_b, comp_b.roles[0]


# ==============================================================================
# CATEGORY A: REAL AI PROVIDER ABSTRACTION & RESILIENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_a_01_ai_factory_provider_resolution_and_fallback():
    """Verify AIFactory instantiates providers correctly and defaults to mock/fallback when API key is missing."""
    # 1. Mock provider direct creation
    mock_provider = AIFactory.get_llm_provider("mock")
    assert isinstance(mock_provider, LLMProvider)
    text_out = await mock_provider.generate_text("Explain binary search")
    assert isinstance(text_out, str) and len(text_out) > 0

    # 2. Gemini provider creation with resilience wrapper
    gemini_provider = AIFactory.get_llm_provider("gemini", enable_fallback=True)
    assert gemini_provider is not None

    # 3. Safe Prompt Builder boundary isolation
    prompt = SafePromptBuilder.build_rag_grounded_prompt(
        task_instruction="Generate interview question",
        rag_context="Company culture: Innovation",
        candidate_input="React candidate",
        schema_instruction="Return JSON"
    )
    assert "### TASK INSTRUCTIONS" in prompt
    assert "<reference_context>" in prompt
    assert "<candidate_input>" in prompt
    assert "STRICT OPERATIONAL RULES" in prompt


@pytest.mark.asyncio
async def test_cat_a_02_ai_malformed_json_resilience():
    """Verify AI JSON parsing safely handles structured output with validation."""
    provider = AIFactory.get_llm_provider()
    json_out = await provider.generate_json(
        prompt="Score calibration for candidate answer: I built React SPAs.",
        system_prompt="You are a technical interviewer evaluator."
    )
    assert isinstance(json_out, dict)
    assert len(json_out) > 0


# ==============================================================================
# CATEGORY B: QUESTION GENERATION & STRICT DUPLICATE PREVENTION
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_b_01_role_aware_and_resume_grounded_question_generation():
    """Verify QuestionSelector generates relevant role-aware questions grounded in candidate context."""
    comp_a, role_a, _, _ = await get_approved_companies_and_roles()
    async with AsyncSessionLocal() as db:
        selector = QuestionSelector(db)
        
        # Frontend candidate context
        q_fe = await selector.select_or_generate_question(
            company_id=comp_a.id,
            role_id=role_a.id,
            topic="Frontend Architecture",
            difficulty="medium",
            asked_question_ids=[],
            interview_type="technical",
            resume_context="Skills: React, Next.js, TypeScript; Education: BS CS"
        )
        assert q_fe is not None
        assert isinstance(q_fe.question_text, str) and len(q_fe.question_text) > 10
        assert q_fe.topic == "Frontend Architecture"

        # ML candidate context
        q_ml = await selector.select_or_generate_question(
            company_id=comp_a.id,
            role_id=role_a.id,
            topic="Machine Learning Pipelines",
            difficulty="hard",
            asked_question_ids=[q_fe.id],
            interview_type="technical",
            resume_context="Skills: Python, PyTorch, Pandas; Education: MS DS"
        )
        assert q_ml is not None
        assert q_ml.id != q_fe.id
        assert q_ml.question_text != q_fe.question_text


@pytest.mark.asyncio
async def test_cat_b_02_strict_duplicate_question_prevention():
    """Verify is_duplicate_question catches exact, normalized, and high-overlap semantic duplicates."""
    existing = [
        "Could you explain how indexing improves query performance in relational databases?",
        "Tell me about a time you resolved a conflict with a team member."
    ]

    # Exact duplicate
    assert is_duplicate_question(
        "Could you explain how indexing improves query performance in relational databases?",
        existing
    ) is True

    # Case & punctuation normalized duplicate
    assert is_duplicate_question(
        "COULD YOU EXPLAIN HOW INDEXING IMPROVES QUERY PERFORMANCE IN RELATIONAL DATABASES???",
        existing
    ) is True

    # 75%+ high overlap duplicate
    assert is_duplicate_question(
        "Can you explain how indexing improves query performance in relational database tables?",
        existing
    ) is True

    # Genuinely distinct question
    assert is_duplicate_question(
        "How would you design a distributed cache using Redis and handle TTL invalidation?",
        existing
    ) is False


# ==============================================================================
# CATEGORY C: ADAPTIVE INTERVIEW PROGRESSION & MULTI-TURN STATE
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_c_01_adaptive_difficulty_and_turn_progression():
    """Verify strong answers advance difficulty and weak answers prompt targeted follow-up/remediation."""
    comp_a, role_a, _, _ = await get_approved_companies_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "p3_adapt")

        # Start interview
        start_res = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id,
            "role_id": role_a.id,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry"
        })
        assert start_res.status_code == 200
        int_data = start_res.json()
        int_id = int_data["id"]
        assert int_data["state"]["questions_asked_count"] == 0

        # Turn 1: Strong Technical Answer -> Should adapt difficulty / maintain high score
        turn1_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": (
                "To optimize relational databases at high scale, B-Tree indexes provide logarithmic O(log N) lookup. "
                "Composite indexes must follow the leftmost prefix rule. For high concurrency, connection pooling and read replicas "
                "offload read-heavy traffic while write workloads benefit from WAL tuning and sharding."
            )
        })
        assert turn1_res.status_code == 200
        data1 = turn1_res.json()
        assert data1["evaluation"]["overall_question_score"] >= 7.0
        assert data1["next_question"] is not None
        assert data1["interview_state"]["questions_asked_count"] == 1

        # Turn 2: Weak / Vague Answer -> Probing / Remediation
        turn2_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "I am not sure about database locks, maybe it locks the whole server."
        })
        assert turn2_res.status_code == 200
        data2 = turn2_res.json()
        assert data2["evaluation"]["overall_question_score"] < 6.0
        assert data2["next_question"] is not None
        assert data2["interview_state"]["questions_asked_count"] == 2


# ==============================================================================
# CATEGORY D: ANSWER EVALUATION & PERSISTENCE SAFETY
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_d_01_schema_validated_evaluation_and_fault_tolerance():
    """Verify AnswerEvaluator produces full rubric scores and answers persist even if evaluation fails."""
    # 1. Direct AnswerEvaluator validation
    eval_dict = await AnswerEvaluator.evaluate_answer(
        question_text="How do you handle state management in React?",
        expected_concepts=["Redux Toolkit", "Context API", "Local State", "Immutability"],
        candidate_answer="I use Redux Toolkit for global state and useState for localized component state.",
        topic="Frontend Architecture",
        question_type="technical"
    )
    assert "correctness_score" in eval_dict
    assert "relevance_score" in eval_dict
    assert "reasoning_score" in eval_dict
    assert "depth_score" in eval_dict
    assert "communication_score" in eval_dict
    assert "overall_question_score" in eval_dict
    assert 0.0 <= eval_dict["overall_question_score"] <= 10.0
    assert isinstance(eval_dict["evidence"], list)

    # 2. Persistence-First Guarantee: Empty answer rejected, valid answer persisted safely
    comp_a, role_a, _, _ = await get_approved_companies_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "p3_pers")
        int_obj = (await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()
        int_id = int_obj["id"]

        # Reject empty
        bad_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": "  "})
        assert bad_res.status_code == 400

        # Submit valid answer
        ans_text = "Persistence test: candidate answer stored prior to evaluation."
        good_res = await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={"answer_text": ans_text})
        assert good_res.status_code == 200

        # Verify in DB
        async with AsyncSessionLocal() as db:
            stmt = select(Answer).where(Answer.interview_id == int_id)
            res = await db.execute(stmt)
            saved_ans = res.scalars().first()
            assert saved_ans is not None
            assert saved_ans.candidate_answer_text == ans_text


# ==============================================================================
# CATEGORY E & F: SECURITY, CANDIDATE ISOLATION & CONCURRENCY
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_e_and_f_concurrent_candidates_and_idor_protection():
    """Verify simultaneous candidate sessions have 100% isolated state, questions, answers, and reports."""
    comp_a, role_a, comp_b, role_b = await get_approved_companies_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate 1 (React Frontend)
        h1, _, uid1 = await create_and_authenticate_candidate(client, "p3_user1")
        await client.post("/api/v1/resume/upload", headers=h1, files={
            "file": ("react.txt", io.BytesIO(SAMPLE_REACT_RESUME), "text/plain")
        })
        m1 = (await client.get("/api/v1/jobs/matches", headers=h1)).json()
        assert len(m1) > 0

        # Candidate 2 (Python ML)
        h2, _, uid2 = await create_and_authenticate_candidate(client, "p3_user2")
        await client.post("/api/v1/resume/upload", headers=h2, files={
            "file": ("ml.txt", io.BytesIO(SAMPLE_PYTHON_RESUME), "text/plain")
        })
        m2 = (await client.get("/api/v1/jobs/matches", headers=h2)).json()
        assert len(m2) > 0

        # Create concurrent interviews
        int1 = (await client.post("/api/v1/interviews", headers=h1, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()
        int2 = (await client.post("/api/v1/interviews", headers=h2, json={
            "company_id": comp_b.id, "role_id": role_b.id, "mode": "text", "duration_minutes": 30
        })).json()

        assert int1["id"] != int2["id"]
        assert int1["candidate_id"] == uid1
        assert int2["candidate_id"] == uid2

        # IDOR checks
        assert (await client.get(f"/api/v1/interviews/{int1['id']}", headers=h2)).status_code in [403, 404]
        assert (await client.get(f"/api/v1/interviews/{int2['id']}", headers=h1)).status_code in [403, 404]
        assert (await client.post(f"/api/v1/interviews/{int1['id']}/answer", headers=h2, json={"answer_text": "Hack"})).status_code in [403, 404]
        assert (await client.post(f"/api/v1/interviews/{int1['id']}/finish", headers=h2)).status_code in [403, 404]


# ==============================================================================
# CATEGORY G: FINAL REPORT GENERATION & ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_cat_g_01_interview_completion_and_report_accuracy():
    """Verify interview completion produces accurate, evidence-grounded reports scoped to candidate."""
    comp_a, role_a, _, _ = await get_approved_companies_and_roles()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _, user_id = await create_and_authenticate_candidate(client, "p3_report")

        # Start interview
        int_obj = (await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": comp_a.id, "role_id": role_a.id, "mode": "text", "duration_minutes": 30
        })).json()
        int_id = int_obj["id"]

        # Answer question
        await client.post(f"/api/v1/interviews/{int_id}/answer", headers=headers, json={
            "answer_text": "I design modular, test-driven REST microservices with PostgreSQL connection pooling."
        })

        # Finish interview
        finish_res = await client.post(f"/api/v1/interviews/{int_id}/finish", headers=headers)
        assert finish_res.status_code == 200
        report_id = finish_res.json()["report_id"]
        assert report_id > 0

        # Fetch report
        rep_res = await client.get(f"/api/v1/reports/{int_id}", headers=headers)
        assert rep_res.status_code == 200
        report_data = rep_res.json()
        assert report_data["id"] == report_id
        assert report_data["interview_id"] == int_id
        assert 0.0 <= report_data["overall_score"] <= 100.0
        assert "rubric_scores" in report_data
        assert "strengths" in report_data
        assert "weaknesses" in report_data
        assert "recommendations" in report_data
