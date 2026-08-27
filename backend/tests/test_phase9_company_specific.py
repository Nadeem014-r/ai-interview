"""Phase 9: Comprehensive Test Suite for Production-Grade Company-Specific Interview Engine.

Validates:
1. Strongly-typed CompanyProfile and RoleProfile retrieval
2. Company differentiation: Same candidate & role produces distinct strategies for Google, Amazon, Microsoft, Oracle, Accenture
3. Role differentiation: Same company produces distinct strategies for Frontend, Backend, ML, Data
4. Seniority differentiation: Entry vs Senior depth and question strategy
5. Competency weighting and difficulty computation
6. Phase 7 memory and Phase 8 project claim integration
7. Fallback safety for unsupported companies, roles, and AI failures
8. Repetition prevention across multi-turn interviews
"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Interview, InterviewState, Question, Answer, Evaluation, Company, Role, User
from app.companies.profiles import COMPANY_PROFILES, GENERIC_COMPANY_PROFILE, CompanyProfile
from app.companies.role_profiles import ROLE_PROFILES, GENERIC_ROLE_PROFILE, RoleProfile
from app.companies.strategy_engine import CompanyStrategyEngine, InterviewStrategy
from app.interview.memory import InterviewMemory, CandidateClaim, ProjectMemory
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.question_selector import QuestionSelector


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def test_phase9_company_profiles_loading():
    """Verify all 10 approved companies plus consulting profiles are properly defined."""
    required_companies = [
        "google", "amazon", "microsoft", "meta", "apple",
        "netflix", "adobe", "oracle", "ibm", "infosys",
        "accenture", "tcs", "deloitte"
    ]
    for comp in required_companies:
        profile = CompanyStrategyEngine.get_company_profile(comp)
        assert profile is not None
        assert profile.company_id == comp
        assert profile.technical_depth >= 7.0
        assert len(profile.competency_weights) >= 3
        assert profile.evidence_level in ["HIGH", "MEDIUM", "LOW"]


def test_phase9_role_profiles_loading():
    """Verify standard engineering role profiles are available."""
    required_roles = ["backend", "frontend", "ml", "data", "devops", "fullstack", "software_engineer"]
    for r in required_roles:
        profile = CompanyStrategyEngine.get_role_profile(r)
        assert profile is not None
        assert profile.role_family == r
        assert len(profile.core_competencies) >= 3
        assert len(profile.key_technologies) >= 3


def test_phase9_company_differentiation_same_candidate():
    """
    Core Behavioral Requirement:
    Same candidate, same role (Backend Engineer), same level (Entry).
    Different companies MUST produce different strategies and question focus.
    """
    strat_google = CompanyStrategyEngine.compute_interview_strategy(
        company_slug_or_name="google",
        role_title="Backend Engineer",
        candidate_level="entry"
    )
    strat_amazon = CompanyStrategyEngine.compute_interview_strategy(
        company_slug_or_name="amazon",
        role_title="Backend Engineer",
        candidate_level="entry"
    )
    strat_oracle = CompanyStrategyEngine.compute_interview_strategy(
        company_slug_or_name="oracle",
        role_title="Backend Engineer",
        candidate_level="entry"
    )
    strat_accenture = CompanyStrategyEngine.compute_interview_strategy(
        company_slug_or_name="accenture",
        role_title="Backend Engineer",
        candidate_level="entry"
    )

    # Google emphasizes algorithmic depth & data structures
    assert strat_google.coding_weight >= 0.9
    assert "algorithmic" in strat_google.company_emphasis

    # Amazon emphasizes system design & leadership / operational principles
    assert strat_amazon.behavioral_weight >= 0.9
    assert strat_amazon.system_design_weight >= 0.9

    # Oracle emphasizes database internals & concurrency
    assert strat_oracle.company_id == "oracle"

    # Accenture emphasizes applied scenarios and problem solving
    assert "applied" in strat_accenture.company_emphasis or "scenario" in strat_accenture.company_emphasis

    # Questions generated must differ
    q_google = CompanyStrategyEngine.generate_deterministic_company_question(strat_google, memory=None)
    q_amazon = CompanyStrategyEngine.generate_deterministic_company_question(strat_amazon, memory=None)
    q_oracle = CompanyStrategyEngine.generate_deterministic_company_question(strat_oracle, memory=None)

    assert q_google["question_text"] != q_amazon["question_text"]
    assert q_google["question_text"] != q_oracle["question_text"]
    assert "data structure" in q_google["question_text"].lower() or "complexity" in q_google["question_text"].lower()
    assert "failure" in q_amazon["question_text"].lower() or "unreachable" in q_amazon["question_text"].lower()
    assert "b-tree" in q_oracle["question_text"].lower() or "transaction" in q_oracle["question_text"].lower()


def test_phase9_role_differentiation_same_company():
    """
    Same company (Google), different roles (Frontend vs Backend vs ML).
    Strategy and questions MUST reflect the domain.
    """
    strat_be = CompanyStrategyEngine.compute_interview_strategy("google", "Backend Engineer", "mid")
    strat_fe = CompanyStrategyEngine.compute_interview_strategy("google", "Frontend Engineer", "mid")
    strat_ml = CompanyStrategyEngine.compute_interview_strategy("google", "Machine Learning Engineer", "mid")

    assert strat_be.role_id == "backend"
    assert strat_fe.role_id == "frontend"
    assert strat_ml.role_id == "ml"

    q_be = CompanyStrategyEngine.generate_deterministic_company_question(strat_be, memory=None)
    q_fe = CompanyStrategyEngine.generate_deterministic_company_question(strat_fe, memory=None)
    q_ml = CompanyStrategyEngine.generate_deterministic_company_question(strat_ml, memory=None)

    assert q_be["question_text"] != q_fe["question_text"]
    assert q_fe["question_text"] != q_ml["question_text"]
    assert "react" in q_fe["question_text"].lower() or "dom" in q_fe["question_text"].lower()
    assert "loss" in q_ml["question_text"].lower() or "overfitting" in q_ml["question_text"].lower()


def test_phase9_seniority_differentiation():
    """
    Same company (Google), same role (Backend), different levels (Entry vs Senior).
    Senior must have higher desired difficulty, higher max depth, and system design emphasis.
    """
    strat_entry = CompanyStrategyEngine.compute_interview_strategy("google", "Backend Engineer", "entry")
    strat_senior = CompanyStrategyEngine.compute_interview_strategy("google", "Backend Engineer", "senior")

    assert strat_senior.desired_difficulty > strat_entry.desired_difficulty
    assert strat_senior.max_depth > strat_entry.max_depth

    q_entry = CompanyStrategyEngine.generate_deterministic_company_question(strat_entry, memory=None)
    q_senior = CompanyStrategyEngine.generate_deterministic_company_question(strat_senior, memory=None)

    assert q_entry["question_text"] != q_senior["question_text"]
    assert "distributed" in q_senior["question_text"].lower() or "rate limiter" in q_senior["question_text"].lower()


def test_phase9_unsupported_company_and_role_fallback():
    """Verify robust fallback when given an unknown company or role."""
    strat = CompanyStrategyEngine.compute_interview_strategy("UnknownCorpX", "Quantum Architect", "entry")
    assert strat.company_id == "generic"
    assert strat.role_id == "software_engineer"
    assert strat.desired_difficulty >= 6.0

    q_fallback = CompanyStrategyEngine.generate_deterministic_company_question(strat, memory=None)
    assert q_fallback is not None
    assert len(q_fallback["question_text"]) > 10


@pytest.mark.asyncio
async def test_phase9_company_memory_and_project_claims_integration():
    """Verify company strategy grounds questions in candidate's Phase 7 memory and Phase 8 claims."""
    memory = InterviewMemory(interview_id=10)
    memory.skills = ["FastAPI", "Redis", "PostgreSQL"]
    memory.projects["PaymentGateway"] = ProjectMemory(
        name="PaymentGateway",
        technologies=["FastAPI", "Redis", "PostgreSQL"],
        description="High-scale payment gateway"
    )

    strat = CompanyStrategyEngine.compute_interview_strategy("amazon", "Backend Engineer", "mid", memory=memory)
    q_data = CompanyStrategyEngine.generate_deterministic_company_question(strat, memory=memory)

    assert "redis" in q_data["question_text"].lower() or "fastapi" in q_data["question_text"].lower()
    assert "failure" in q_data["question_text"].lower() or "unreachable" in q_data["question_text"].lower()


@pytest.mark.asyncio
async def test_phase9_multi_turn_company_interview(async_db: AsyncSession):
    """Verify end-to-end multi-turn interview execution respecting company and role strategies."""
    company = Company(
        name="Google",
        slug="google",
        description="Search and systems",
        culture_keywords=["Scale", "Algorithms", "Clean Code"]
    )
    async_db.add(company)
    await async_db.commit()
    await async_db.refresh(company)

    role = Role(
        company_id=company.id,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        key_topics=["Algorithms", "Data Structures", "Distributed Systems"]
    )
    async_db.add(role)
    await async_db.commit()
    await async_db.refresh(role)

    user = User(full_name="Jordan Lee", email="jordan.lee@example.com", hashed_password="pw", role="candidate")
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    interview = Interview(
        candidate_id=user.id,
        company_id=company.id,
        role_id=role.id,
        interview_type="technical",
        duration_minutes=30,
        status="in_progress"
    )
    async_db.add(interview)
    await async_db.commit()
    await async_db.refresh(interview)

    selector = QuestionSelector(async_db)
    memory = InterviewMemory(interview_id=interview.id)

    # Turn 1: Generate initial company question
    q1 = await selector.select_or_generate_question(
        company_id=company.id,
        role_id=role.id,
        topic="Data Structures",
        difficulty="medium",
        asked_question_ids=[],
        memory=memory
    )
    assert q1 is not None
    assert len(q1.question_text) > 15

    # Turn 2: Generate subsequent company question with repetition prevention
    memory.asked_question_texts.append(q1.question_text)
    q2 = await selector.select_or_generate_question(
        company_id=company.id,
        role_id=role.id,
        topic="Distributed Systems",
        difficulty="medium",
        asked_question_ids=[q1.id],
        memory=memory
    )
    assert q2 is not None
    assert q2.id != q1.id
    assert q2.question_text != q1.question_text


@pytest.mark.asyncio
async def test_phase9_llm_failure_fallback():
    """Verify that if LLM raises an exception, CompanyStrategyEngine falls back safely."""
    strat = CompanyStrategyEngine.compute_interview_strategy("google", "Backend Engineer", "mid")
    with patch("app.ai.factory.AIFactory.get_llm_provider") as mock_factory:
        mock_llm = AsyncMock()
        mock_llm.generate_json.side_effect = ConnectionError("AI provider unreachable")
        mock_factory.return_value = mock_llm

        res = await CompanyStrategyEngine.generate_adaptive_company_question(
            strategy=strat,
            memory=None,
            candidate_answer="I designed a caching layer using Redis."
        )

        assert res is not None
        assert "question_text" in res
        assert len(res["question_text"]) > 10
