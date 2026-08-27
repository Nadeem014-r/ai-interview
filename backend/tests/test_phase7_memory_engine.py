"""Phase 7: Comprehensive Test Suite for Structured Interview Memory & Adaptive Follow-Up Engine.

Validates:
1. Structured memory extraction (candidate profile, skills, projects, candidate assertions/claims).
2. Contextual follow-up generation referencing previous answers (FastAPI, Redis, PostgreSQL, JWT).
3. Semantic repetition prevention (exact and fuzzy overlap).
4. Adaptive depth escalation on strong answers and recovery on weak/evasive answers.
5. Multi-turn coherence across consecutive questions.
6. Resilient deterministic fallbacks on LLM failures.
"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Interview, InterviewState, Question, Answer, Evaluation, Company, Role, Resume, ResumeProfile, User
from app.interview.memory import InterviewMemory, MemoryManager, CandidateClaim, ProjectMemory
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
async def test_memory_manager_build_and_extraction():
    """Verify initial memory construction from resume and entity/claim extraction."""
    mock_resume_profile = {
        "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
        "projects": [
            {
                "name": "AI Interviewer",
                "technologies": ["FastAPI", "PostgreSQL", "Redis", "Next.js"],
                "description": "Full-stack real-time mock interview simulator."
            }
        ]
    }

    memory = MemoryManager.build_initial_memory(
        interview_id=101,
        role_key_topics=["Database Indexing", "System Design", "Concurrency"],
        resume_profile=mock_resume_profile
    )

    assert memory.interview_id == 101
    assert "FastAPI" in memory.skills
    assert "AI Interviewer" in memory.projects
    assert len(memory.claims) >= 1
    assert "Database Indexing" in memory.unexplored_topics

    # Extract claims from candidate answer
    answer = "In my project I used Redis for caching session data to minimize database queries."
    techs, claim = MemoryManager.extract_technical_entities_and_claims(
        answer_text=answer,
        question_text="How did you structure caching?",
        topic="Caching & Performance",
        turn_index=1
    )

    assert "Redis" in techs
    assert claim is not None
    assert "redis" in claim.claim_text.lower()
    assert claim.follow_up_hook is not None


@pytest.mark.asyncio
async def test_candidate_claim_probing_redis():
    """Verify engine generates targeted follow-up on Redis caching claim."""
    memory = InterviewMemory(interview_id=1)
    MemoryManager.ingest_turn(
        memory=memory,
        question_text="How did you optimize API performance?",
        candidate_answer="I used Redis for caching to prevent hitting PostgreSQL on every interview state request.",
        eval_dict={"overall_question_score": 7.5, "depth_score": 6.0, "demonstrated_concepts": ["Redis Caching"]},
        topic="Caching & Performance"
    )

    follow_up = FollowUpEngine.generate_deterministic_follow_up(
        topic="Caching & Performance",
        reason_category="probe_candidate_claim",
        candidate_answer="I used Redis for caching to prevent hitting PostgreSQL on every interview state request.",
        memory=memory
    )

    assert "redis" in follow_up["question_text"].lower()
    assert "cache invalidation" in follow_up["question_text"].lower() or "stampede" in follow_up["question_text"].lower()


@pytest.mark.asyncio
async def test_candidate_claim_probing_fastapi_postgres():
    """Verify engine generates targeted follow-up on FastAPI + PostgreSQL claim."""
    memory = InterviewMemory(interview_id=2)
    MemoryManager.ingest_turn(
        memory=memory,
        question_text="Tell me about your backend architecture.",
        candidate_answer="I built the backend using FastAPI with PostgreSQL for storing interview sessions and audio logs.",
        eval_dict={"overall_question_score": 8.0, "depth_score": 7.0, "demonstrated_concepts": ["FastAPI", "PostgreSQL"]},
        topic="Backend Architecture"
    )

    follow_up = FollowUpEngine.generate_deterministic_follow_up(
        topic="Backend Architecture",
        reason_category="probe_candidate_claim",
        candidate_answer="I built the backend using FastAPI with PostgreSQL for storing interview sessions.",
        memory=memory
    )

    assert "fastapi" in follow_up["question_text"].lower() or "postgres" in follow_up["question_text"].lower()
    assert "database" in follow_up["question_text"].lower() or "sqlalchemy" in follow_up["question_text"].lower()


@pytest.mark.asyncio
async def test_evasive_weak_answer_recovery():
    """Verify engine asks gentle foundational question on evasive/unknown answers without crashing."""
    follow_up = FollowUpEngine.generate_deterministic_follow_up(
        topic="Database Indexing",
        reason_category="i_dont_know_foundation",
        candidate_answer="I don't know much about database indexes, honestly."
    )

    assert "database indexing" in follow_up["question_text"].lower() or "fundamentals" in follow_up["question_text"].lower() or "core problem" in follow_up["question_text"].lower()


@pytest.mark.asyncio
async def test_strong_answer_escalation():
    """Verify engine escalates to scale, concurrency, and trade-offs on strong answers."""
    follow_up = FollowUpEngine.generate_deterministic_follow_up(
        topic="Hash Tables",
        reason_category="strong_answer_tradeoffs",
        candidate_answer="Hash tables provide O(1) average lookup by mapping keys through a hash function to array buckets, resolving collisions via chaining."
    )

    assert "collide" in follow_up["question_text"].lower() or "concurrency" in follow_up["question_text"].lower() or "scale" in follow_up["question_text"].lower() or "bottleneck" in follow_up["question_text"].lower()


@pytest.mark.asyncio
async def test_repetition_prevention_semantic():
    """Verify semantic and lexical repetition prevention."""
    existing = [
        "How do database indexes improve query execution speed, and what are the trade-offs on write operations?",
        "Can you explain the mechanics of JWT token signing and verification?"
    ]

    # Exact duplicate
    assert is_duplicate_question("How do database indexes improve query execution speed, and what are the trade-offs on write operations?", existing)

    # Near duplicate with minor phrasing variation
    assert is_duplicate_question("How do database indexes improve query execution speed and what are the write trade-offs?", existing)

    # Completely different question
    assert not is_duplicate_question("What is the difference between TCP and UDP protocols?", existing)


@pytest.mark.asyncio
async def test_multi_turn_interview_coherence(async_db: AsyncSession):
    """Verify 5-turn multi-turn interview progression with memory tracking and zero repetition."""
    # Seed company, role, user, and interview
    company = Company(name="CloudCorp", slug="cloudcorp", description="Cloud infrastructure")
    async_db.add(company)
    await async_db.commit()
    await async_db.refresh(company)

    role = Role(
        company_id=company.id,
        title="Backend Software Engineer",
        level="L3/Entry",
        key_topics=["Database Indexing", "API Security", "Caching & Concurrency", "System Architecture"]
    )
    async_db.add(role)
    await async_db.commit()
    await async_db.refresh(role)

    user = User(full_name="Candidate One", email="candidate1@test.com", hashed_password="hash123", role="candidate")
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
    state = await engine.initialize_interview_state(
        interview=interview,
        key_topics=role.key_topics
    )

    asked_ids = []
    turns_answers = [
        "In my previous project I built an API using FastAPI with PostgreSQL for persistence.",
        "To speed up lookups I implemented B-Tree indexes on foreign keys, which reduced query time significantly.",
        "For caching frequently accessed user profiles I used Redis with a 5-minute TTL.",
        "For security we implemented JWT tokens with cryptographic signatures and HttpOnly cookies.",
        "When scaling across multiple instances we used Kubernetes with horizontal pod autoscaling."
    ]

    for idx, ans_text in enumerate(turns_answers):
        state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=8.2,
            asked_question_ids=asked_ids,
            last_eval_dict={"overall_question_score": 8.2, "depth_score": 7.5, "feedback_text": "Strong answer."},
            last_answer_text=ans_text
        )

        assert not is_completed
        assert next_q is not None
        assert next_q.question_text is not None
        assert len(next_q.question_text) > 15
        asked_ids.append(next_q.id)

    # Verify all 5 generated questions are unique
    stmt = await async_db.execute(Question.__table__.select().where(Question.id.in_(asked_ids)))
    q_rows = stmt.fetchall()
    q_texts = [r.question_text for r in q_rows]
    assert len(set(q_texts)) == len(q_texts), "All generated questions must be unique!"


@pytest.mark.asyncio
async def test_fallback_on_llm_failure():
    """Verify that if LLM fails, FollowUpEngine and QuestionSelector fallback gracefully."""
    with patch("app.ai.factory.AIFactory.get_llm_provider") as mock_factory:
        mock_llm = AsyncMock()
        mock_llm.generate_json.side_effect = RuntimeError("API connection timeout")
        mock_factory.return_value = mock_llm

        res = await FollowUpEngine.generate_adaptive_follow_up(
            topic="Database Indexing",
            question_text="How do indexes work?",
            candidate_answer="They speed up queries.",
            eval_feedback="Vague answer",
            reason_category="vague_answer"
        )

        assert res is not None
        assert "question_text" in res
        assert len(res["question_text"]) > 10
