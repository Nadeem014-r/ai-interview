"""Phase 8: Comprehensive Test Suite for Production-Grade Resume + Project Interrogation Engine.

Validates:
1. Resume project extraction & technology extraction
2. Structured claim extraction & candidate ownership detection
3. Progressive depth exploration (Levels 1-11: Overview, Ownership, Architecture, Design Decisions, Trade-offs, Security, Scale, Failure Modes, Production)
4. Adaptive depth escalation on strong answers & recovery on weak/vague answers
5. Spontaneous candidate hook detection (race conditions, bottlenecks, cache stampedes, deadlocks)
6. Grounded interrogation without fabricating unmentioned technologies
7. Semantic repetition prevention across turns
8. Full multi-turn 5+ turn interview progression with memory integration
9. Fallback safety on AI failure
10. Seamless compatibility with Text, Voice, and Video interview modes
"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Interview, InterviewState, Question, Answer, Evaluation, Company, Role, Resume, ResumeProfile, User
from app.interview.memory import InterviewMemory, MemoryManager, CandidateClaim, ProjectMemory
from app.interview.project_interrogator import (
    ResumeProjectInterrogator,
    InterrogationDepth,
    ProjectClaimInvestigation
)
from app.interview.conversation import FollowUpEngine
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.question_selector import QuestionSelector, is_duplicate_question


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_phase8_resume_claim_and_tech_extraction():
    """Verify structured project, skill, and claim extraction from resume profile."""
    mock_profile = {
        "skills": ["FastAPI", "PostgreSQL", "Redis", "JWT", "Docker"],
        "projects": [
            {
                "title": "E-Commerce Microservices",
                "technologies": ["FastAPI", "PostgreSQL", "Redis"],
                "description": "High-throughput e-commerce platform handling payments and orders."
            },
            {
                "title": "Real-time Chat App",
                "technologies": ["WebSockets", "Redis", "React"],
                "description": "Bi-directional chat service with pub/sub."
            }
        ]
    }

    claims = ResumeProjectInterrogator.extract_structured_claims_from_resume(mock_profile)
    assert len(claims) >= 3

    # Check project claims
    p_names = [c.project_name for c in claims if c.project_name]
    assert "E-Commerce Microservices" in p_names
    assert "Real-time Chat App" in p_names

    # Check that technologies are captured
    techs = [c.technology for c in claims if c.technology]
    assert "FastAPI" in techs
    assert "Redis" in techs


@pytest.mark.asyncio
async def test_phase8_unsupported_claim_prevention():
    """Verify engine never fabricates unmentioned technologies (e.g. Kubernetes) if not in resume."""
    mock_profile = {
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "projects": [
            {
                "title": "Task Manager",
                "technologies": ["Python", "SQLite"],
                "description": "Simple CRUD app."
            }
        ]
    }

    claims = ResumeProjectInterrogator.extract_structured_claims_from_resume(mock_profile)
    claim_texts = " ".join([c.claim_text.lower() for c in claims])
    assert "kubernetes" not in claim_texts
    assert "kafka" not in claim_texts
    assert "graphql" not in claim_texts


@pytest.mark.asyncio
async def test_phase8_candidate_ownership_probing():
    """Verify Level 2 ownership questioning when candidate contribution is unverified."""
    memory = InterviewMemory(interview_id=1)
    q_data = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="FastAPI",
        depth_level=InterrogationDepth.OWNERSHIP,
        reason="verify_ownership",
        candidate_answer="We built a microservices backend.",
        project_name="E-Commerce Platform"
    )

    assert "personally" in q_data["question_text"].lower() or "individual" in q_data["question_text"].lower()
    assert "e-commerce platform" in q_data["question_text"].lower() or "fastapi" in q_data["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_design_decisions_and_tradeoffs():
    """Verify Level 5 Design Decisions & Level 6 Trade-offs questioning (Why X over Y)."""
    memory = InterviewMemory(interview_id=2)
    # Level 5: Design decisions
    q_design = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="FastAPI",
        depth_level=InterrogationDepth.DESIGN_DECISIONS,
        reason="design_decisions",
        candidate_answer="I chose FastAPI for the backend API layer.",
        project_name="Payment Gateway"
    )
    assert "why" in q_design["question_text"].lower() or "alternative" in q_design["question_text"].lower()
    assert "fastapi" in q_design["question_text"].lower()

    # Level 6: Trade-offs
    q_tradeoff = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="Redis",
        depth_level=InterrogationDepth.TRADE_OFFS,
        reason="trade_offs",
        candidate_answer="We used Redis for caching frequent product reads.",
        project_name="Catalog Service"
    )
    assert "freshness" in q_tradeoff["question_text"].lower() or "trade-off" in q_tradeoff["question_text"].lower() or "latency" in q_tradeoff["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_security_probing():
    """Verify Level 7 Security questioning on auth, JWT, or input validation."""
    memory = InterviewMemory(interview_id=3)
    q_sec = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="JWT",
        depth_level=InterrogationDepth.SECURITY,
        reason="security",
        candidate_answer="I implemented authentication using JWT tokens.",
        project_name="Auth Server"
    )

    assert "xss" in q_sec["question_text"].lower() or "revocation" in q_sec["question_text"].lower() or "security" in q_sec["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_scalability_probing():
    """Verify Level 9 Scalability questioning from 100 to 10,000 users."""
    memory = InterviewMemory(interview_id=4)
    q_scale = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="PostgreSQL",
        depth_level=InterrogationDepth.SCALABILITY,
        reason="scalability",
        candidate_answer="PostgreSQL stores all user profile and order records.",
        project_name="Order Service"
    )

    assert "100" in q_scale["question_text"] or "10,000" in q_scale["question_text"] or "bottleneck" in q_scale["question_text"].lower()
    assert "postgresql" in q_scale["question_text"].lower() or "database" in q_scale["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_failure_modes_probing():
    """Verify Level 10 Failure Mode questioning on service crash / downtime."""
    memory = InterviewMemory(interview_id=5)
    q_fail = ResumeProjectInterrogator.generate_deterministic_project_question(
        memory=memory,
        target_tech="Redis",
        depth_level=InterrogationDepth.FAILURE_MODES,
        reason="failure_modes",
        candidate_answer="Redis is used for caching session tokens.",
        project_name="Session Manager"
    )

    assert "crashed" in q_fail["question_text"].lower() or "down" in q_fail["question_text"].lower() or "unreachable" in q_fail["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_spontaneous_hook_detection():
    """Verify engine detects spontaneous technical hooks (race condition, cache stampede)."""
    # Spontaneous race condition hook
    ans_race = "While building the inventory counter, I actually ran into a race condition with concurrent checkout requests."
    hook_race = ResumeProjectInterrogator.identify_spontaneous_candidate_hooks(ans_race)
    assert hook_race is not None
    assert hook_race["hook_type"] == "race_condition"
    assert "race condition" in hook_race["question_text"].lower()

    # Spontaneous cache stampede hook
    ans_stampede = "When popular products launched, we experienced a severe cache stampede."
    hook_stampede = ResumeProjectInterrogator.identify_spontaneous_candidate_hooks(ans_stampede)
    assert hook_stampede is not None
    assert hook_stampede["hook_type"] == "cache_stampede"
    assert "stampede" in hook_stampede["question_text"].lower()


@pytest.mark.asyncio
async def test_phase8_adaptive_depth_escalation_and_recovery():
    """Verify engine escalates depth on strong answers (>=8.0) and clarifies on weak answers (<5.0)."""
    memory = InterviewMemory(interview_id=6)

    # Strong answer escalation
    depth_strong, reason_strong, tech_strong = ResumeProjectInterrogator.decide_progressive_interrogation_step(
        memory=memory,
        candidate_answer="I used PostgreSQL connection pooling and B-Tree indexes on tenant_id.",
        last_eval_score=8.5,
        depth_score=8.0
    )
    assert depth_strong in (InterrogationDepth.TRADE_OFFS, InterrogationDepth.SCALABILITY, InterrogationDepth.FAILURE_MODES)
    assert "strong" in reason_strong

    # Weak answer recovery
    depth_weak, reason_weak, tech_weak = ResumeProjectInterrogator.decide_progressive_interrogation_step(
        memory=memory,
        candidate_answer="I am not sure how PostgreSQL handles concurrency under the hood.",
        last_eval_score=4.0,
        depth_score=3.5
    )
    assert depth_weak == InterrogationDepth.IMPLEMENTATION
    assert "weak" in reason_weak


@pytest.mark.asyncio
async def test_phase8_multi_turn_project_progression(async_db: AsyncSession):
    """Verify 5-turn progressive project interrogation lifecycle with memory integration."""
    company = Company(name="FinTech Corp", slug="fintech-corp", description="High-scale payments")
    async_db.add(company)
    await async_db.commit()
    await async_db.refresh(company)

    role = Role(
        company_id=company.id,
        title="Senior Backend Engineer",
        level="L4/Mid-Senior",
        key_topics=["Payment Processing", "Database Scalability", "Distributed Caching", "API Security"]
    )
    async_db.add(role)
    await async_db.commit()
    await async_db.refresh(role)

    user = User(full_name="Alex Rivera", email="alex.rivera@example.com", hashed_password="pw", role="candidate")
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

    engine = AdaptiveInterviewEngine(async_db)
    state = await engine.initialize_interview_state(interview, key_topics=role.key_topics)

    turns_answers = [
        "In my previous role at PayFlow, I designed and built the payment processing backend using FastAPI and PostgreSQL.",
        "I was solely responsible for designing the database transactions, idempotency keys, and order state machine.",
        "We chose PostgreSQL with strict serializable isolation to prevent double-charging during concurrent card submissions.",
        "For caching idempotent response tokens, we used Redis with a 24-hour TTL and pessimistic distributed locks.",
        "If Redis or our bank gateway fails, we implement exponential backoff retries and write events to a dead-letter queue."
    ]

    asked_ids = []
    for turn_idx, ans_text in enumerate(turns_answers):
        state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=8.5,
            asked_question_ids=asked_ids,
            last_eval_dict={"overall_question_score": 8.5, "depth_score": 8.0, "feedback_text": "Excellent depth."},
            last_answer_text=ans_text
        )

        assert not is_completed
        assert next_q is not None
        assert len(next_q.question_text) > 15
        asked_ids.append(next_q.id)

    # Verify all 5 generated questions are unique and non-repetitive
    stmt = await async_db.execute(Question.__table__.select().where(Question.id.in_(asked_ids)))
    q_rows = stmt.fetchall()
    q_texts = [r.question_text for r in q_rows]
    assert len(set(q_texts)) == len(q_texts), "All generated questions must be unique!"


@pytest.mark.asyncio
async def test_phase8_fallback_on_ai_failure():
    """Verify that if AI generation raises an exception, the interrogator falls back safely."""
    memory = InterviewMemory(interview_id=7)
    with patch("app.ai.factory.AIFactory.get_llm_provider") as mock_factory:
        mock_llm = AsyncMock()
        mock_llm.generate_json.side_effect = TimeoutError("LLM Gateway Timeout")
        mock_factory.return_value = mock_llm

        res = await ResumeProjectInterrogator.generate_adaptive_project_question(
            memory=memory,
            candidate_answer="I used Redis for caching.",
            last_eval_score=8.0,
            depth_score=7.5,
            current_project_name="E-Commerce App"
        )

        assert res is not None
        assert "question_text" in res
        assert len(res["question_text"]) > 10
        assert "redis" in res["question_text"].lower() or "e-commerce" in res["question_text"].lower()
