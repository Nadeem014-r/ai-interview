"""Focused regression tests for audit issues H1, H2 and H5.

H1 - the HR branch of AnswerEvaluator._deterministic_fallback_evaluation was
     overwritten by a technical-scoring chain that began with its own `if`.
H2 - InterviewState.covered_topics / .remaining_topics are plain JSON columns
     with no MutableList tracking, so in-place append/remove was discarded on
     commit.
H5 - the answer router turned an evaluation failure into a fabricated
     5.0/5.0/5.0/5.0/6.0 -> 5.2 "pass".
R1 - is_explicit_unknown() substring-matched "pass"/"skip", so ordinary
     technical wording ("passwords", "passed by reference", "bypass",
     "skip list") was read as a refusal. EXPLICIT_UNKNOWN short-circuits
     evaluate_answer() before the LLM is called, so those answers were
     returned as a hard 0.0 and could end the interview.

Database safety: every DB-backed test below builds its own throwaway SQLite
engine and overrides the app's get_db dependency. Nothing here connects to the
configured (PostgreSQL) database.
"""

import os
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.db.models import (
    Answer,
    Company,
    Evaluation,
    Interview,
    InterviewState,
    Role,
)
from app.evaluation.evaluator import AnswerEvaluator
from app.evaluation.validation import (
    classify_response_quality_state,
    is_explicit_unknown,
)

fallback = AnswerEvaluator._deterministic_fallback_evaluation

HR_ANSWER = (
    "I am a final year university student and I built a Python and React "
    "application for my college project. I am interested in software engineering."
)
HR_SCORES = (8.0, 8.5, 8.0, 7.0, 8.0)
HR_DEMONSTRATED = ["Personal background", "Role motivation"]

# The exact fabricated evaluation H5 used to persist.
FABRICATED = (5.0, 5.0, 5.0, 5.0, 6.0)
FABRICATED_OVERALL = 5.2


def rubric(result):
    return (
        result["correctness_score"],
        result["relevance_score"],
        result["reasoning_score"],
        result["depth_score"],
        result["communication_score"],
    )


# ======================================================================
# H1 - HR scoring must not be overwritten by technical-depth scoring
# ======================================================================

@pytest.mark.parametrize("question_type,topic", [
    ("hr", "Introduction & Motivation"),
    ("behavioral", "Teamwork"),
])
def test_h1_hr_answer_uses_hr_branch(question_type, topic):
    """An HR/behavioral answer is scored by the HR branch."""
    res = fallback(
        safe_answer=HR_ANSWER,
        expected_concepts=[],
        topic=topic,
        question_type=question_type,
        question_text="Tell me about yourself.",
    )
    assert rubric(res) == HR_SCORES
    assert res["demonstrated_concepts"] == HR_DEMONSTRATED
    assert res["feedback_text"] == "Clear personal background and role motivation provided."


def test_h1_hr_detected_by_topic_even_for_technical_question_type():
    """is_hr also keys off the topic, not only question_type."""
    res = fallback(
        safe_answer=HR_ANSWER,
        expected_concepts=[],
        topic="Introduction & Motivation",
        question_type="technical",
        question_text="Tell me about yourself.",
    )
    assert res["demonstrated_concepts"] == HR_DEMONSTRATED


def test_h1_hr_scores_not_overwritten_by_technical_depth_logic():
    """The regression itself: HR answers carrying technical vocabulary.

    Pre-fix the technical chain ran unconditionally and rescored this to the
    'partial/good' branch (correctness 5.5, demonstrated=[topic]).
    """
    hr_with_tech_vocab = (
        "I am a graduate engineer and my team project used a hash table and a "
        "B+ tree index to reduce disk i/o for our university application."
    )
    res = fallback(
        safe_answer=hr_with_tech_vocab,
        expected_concepts=[],
        topic="Introduction & Motivation",
        question_type="hr",
        question_text="Tell me about yourself.",
    )
    assert res["demonstrated_concepts"] == HR_DEMONSTRATED
    assert rubric(res) == HR_SCORES
    assert res["correctness_score"] != 5.5, "HR scoring was overwritten by the technical branch"


def test_h1_hr_brief_answer_uses_the_brief_hr_tier():
    """The HR branch's own internal tiers still apply."""
    res = fallback(
        safe_answer="I am a graduate interested in software engineering work.",
        expected_concepts=[],
        topic="Introduction & Motivation",
        question_type="hr",
        question_text="Tell me about yourself.",
    )
    assert res["demonstrated_concepts"] == HR_DEMONSTRATED


@pytest.mark.parametrize("label,answer,concepts,expected_correctness", [
    ("strong",
     "A B+ tree index reduces disk i/o with o(log n) lookups but adds write "
     "amplification and page splits on insert.",
     ["B+ tree", "disk I/O", "write amplification"], 9.5),
    ("partial",
     "Indexes make lookup faster by storing keys in a table for search.",
     ["B+ tree", "disk I/O"], 5.5),
    ("weak",
     "It is a thing that helps the database work better somehow.",
     ["B+ tree", "disk I/O"], 2.5),
])
def test_h1_technical_scoring_unchanged(label, answer, concepts, expected_correctness):
    """Non-HR answers keep their existing scoring exactly."""
    res = fallback(
        safe_answer=answer,
        expected_concepts=concepts,
        topic="Database Indexing",
        question_type="technical",
        question_text="Explain database indexing.",
    )
    assert res["correctness_score"] == expected_correctness, label


def test_h1_off_topic_and_misconception_branches_also_survive():
    """These shared the HR branch's chain and were overwritten by the same bug."""
    off_topic = fallback(
        safe_answer="The capital of France is Paris and the weather is nice today.",
        expected_concepts=["B+ tree"],
        topic="Database Indexing",
        question_type="technical",
        question_text="Explain database indexing.",
    )
    assert off_topic["correctness_score"] == 0.0

    misconception = fallback(
        safe_answer=(
            "Database indexes are encrypted copies of the table using rsa keys "
            "for secure lookup."
        ),
        expected_concepts=["B+ tree"],
        topic="Database Indexing",
        question_type="technical",
        question_text="Explain database indexing.",
    )
    assert misconception["misconceptions"], "detected misconceptions were discarded"


# ======================================================================
# Throwaway SQLite fixtures (never touch the configured database)
# ======================================================================

@pytest_asyncio.fixture
async def sqlite_sessionmaker():
    """An isolated on-disk SQLite database with the project's real schema."""
    path = os.path.join(tempfile.gettempdir(), f"h1h2h5_{uuid.uuid4().hex}.sqlite")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    assert engine.dialect.name == "sqlite"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()
        if os.path.exists(path):
            os.remove(path)


@pytest_asyncio.fixture
async def api_client(sqlite_sessionmaker):
    """App client whose get_db resolves to the throwaway SQLite database."""
    from app.main import api_v1, app

    async def _get_db():
        async with sqlite_sessionmaker() as session:
            yield session

    # Routes live on the mounted sub-app, so the override belongs there.
    api_v1.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_db] = _get_db

    async with sqlite_sessionmaker() as db:
        company = Company(name="Regression Corp", slug=f"regression-{uuid.uuid4().hex[:6]}")
        db.add(company)
        await db.flush()
        role = Role(
            company_id=company.id,
            title="Software Engineer (Backend)",
            level="Entry / L3",
            required_skills=["Python", "Data Structures"],
            key_topics=["Data Structures", "Relational Databases"],
            interview_categories=["technical", "hr"],
        )
        db.add(role)
        await db.commit()
        ids = (company.id, role.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=120) as client:
        yield client, ids

    api_v1.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_db, None)


async def _authenticate(client):
    email = f"reg_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
        "full_name": "Regression Candidate", "role": "candidate",
    })
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ======================================================================
# H2 - topic progression must survive commit + reload
# ======================================================================

@pytest.mark.asyncio
async def test_h2_topic_advance_persists_across_commit_and_reload(sqlite_sessionmaker):
    """Advance a topic, commit, then reload in a fresh session."""
    topics = ["Databases", "Networking", "Algorithms"]

    async with sqlite_sessionmaker() as db:
        db.add(InterviewState(
            interview_id=1, current_topic=topics[0], time_remaining_seconds=1800,
            covered_topics=[], remaining_topics=list(topics),
        ))
        await db.commit()

    async with sqlite_sessionmaker() as db:
        state = (await db.execute(select(InterviewState))).scalars().first()
        # Mirrors app/interview/engine.py's topic-advance block.
        state.covered_topics = (state.covered_topics or []) + [state.current_topic]
        remaining = list(state.remaining_topics)
        remaining.remove(state.current_topic)
        state.remaining_topics = remaining
        await db.commit()

    async with sqlite_sessionmaker() as db:  # fresh ORM context
        state = (await db.execute(select(InterviewState))).scalars().first()
        assert state.covered_topics == ["Databases"]
        assert "Databases" not in state.remaining_topics
        assert state.remaining_topics == ["Networking", "Algorithms"]


@pytest.mark.asyncio
async def test_h2_in_place_mutation_is_not_persisted(sqlite_sessionmaker):
    """Documents why the fix is required: the old pattern silently loses data.

    If this ever starts passing with in-place mutation, the columns gained
    mutation tracking and the reassignment in engine.py can be revisited.
    """
    async with sqlite_sessionmaker() as db:
        db.add(InterviewState(
            interview_id=1, current_topic="Databases", time_remaining_seconds=1800,
            covered_topics=[], remaining_topics=["Databases", "Networking"],
        ))
        await db.commit()

    async with sqlite_sessionmaker() as db:
        state = (await db.execute(select(InterviewState))).scalars().first()
        state.covered_topics.append("Databases")      # in-place - untracked
        state.remaining_topics.remove("Databases")    # in-place - untracked
        await db.commit()

    async with sqlite_sessionmaker() as db:
        state = (await db.execute(select(InterviewState))).scalars().first()
        assert state.covered_topics == [], "in-place mutation unexpectedly persisted"
        assert state.remaining_topics == ["Databases", "Networking"]


@pytest.mark.asyncio
async def test_h2_multiple_turns_preserve_order_without_duplicates(sqlite_sessionmaker):
    """Several turns in separate sessions keep ordering and avoid duplicates."""
    topics = ["Databases", "Networking", "Algorithms", "Systems"]

    async with sqlite_sessionmaker() as db:
        db.add(InterviewState(
            interview_id=1, current_topic=topics[0], time_remaining_seconds=1800,
            covered_topics=[], remaining_topics=list(topics),
        ))
        await db.commit()

    for topic in topics + ["Databases"]:  # repeat one topic on purpose
        async with sqlite_sessionmaker() as db:
            state = (await db.execute(select(InterviewState))).scalars().first()
            state.current_topic = topic
            if state.current_topic not in (state.covered_topics or []):
                state.covered_topics = (state.covered_topics or []) + [state.current_topic]
                if state.remaining_topics and state.current_topic in state.remaining_topics:
                    remaining = list(state.remaining_topics)
                    remaining.remove(state.current_topic)
                    state.remaining_topics = remaining
            await db.commit()

    async with sqlite_sessionmaker() as db:
        state = (await db.execute(select(InterviewState))).scalars().first()
        assert state.covered_topics == topics
        assert len(state.covered_topics) == len(set(state.covered_topics))
        assert state.remaining_topics == []
        # The stop condition used by the engine can now observe persisted state.
        all_topics_covered = bool(
            state.covered_topics
            and not state.remaining_topics
            and len(state.covered_topics) >= 3
        )
        assert all_topics_covered is True


@pytest.mark.asyncio
async def test_h2_state_persists_through_the_real_answer_endpoint(api_client, sqlite_sessionmaker):
    """End-to-end: after a real answer turn the DB matches the API response.

    This is the precise H2 divergence: pre-fix the response was built from the
    mutated in-memory object while the committed row still held the old lists.
    """
    client, (company_id, role_id) = api_client
    headers = await _authenticate(client)

    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "mode": "text",
        "interview_type": "technical", "duration_minutes": 30,
    })
    assert created.status_code == 200, created.text
    interview_id = created.json()["id"]

    # NOTE: answers that trigger a follow-up probe currently hit an unrelated
    # pre-existing defect (FollowUpEngine.generate_adaptive_follow_up is
    # missing), which is out of scope here. This answer completes a full turn,
    # so the test exercises the real engine's topic-advance and commit.
    submitted = await client.post(
        f"/api/v1/interviews/{interview_id}/answer", headers=headers,
        json={"answer_text": "It is a thing that helps the database work better somehow."},
    )
    assert submitted.status_code == 200, submitted.text
    reported = submitted.json()["interview_state"]

    async with sqlite_sessionmaker() as db:  # fresh session = real reload
        state = (await db.execute(
            select(InterviewState).where(InterviewState.interview_id == interview_id)
        )).scalars().first()
        assert state is not None
        assert state.covered_topics == reported["covered_topics"], (
            "persisted covered_topics diverged from the response"
        )
        assert state.remaining_topics == reported["remaining_topics"], (
            "persisted remaining_topics diverged from the response"
        )
        # A covered topic must no longer be pending.
        for topic in state.covered_topics:
            assert topic not in state.remaining_topics


# ======================================================================
# H5 - evaluation failure must not become a fabricated passing score
# ======================================================================

def test_h5_deterministic_fallback_never_returns_the_fabricated_rubric():
    """The evaluator's fallback grades the answer instead of passing it."""
    weak = fallback(
        safe_answer="It is a thing that helps the database work better somehow.",
        expected_concepts=["B+ tree", "disk I/O"],
        topic="Database Indexing",
        question_type="technical",
        question_text="Explain database indexing.",
    )
    assert rubric(weak) != FABRICATED
    assert weak["overall_question_score"] != FABRICATED_OVERALL
    assert weak["overall_question_score"] < 5.0, "a weak answer must not score as a pass"


def test_h5_fallback_supplies_the_keys_adaptive_logic_consumes():
    """The old fabricated dict omitted these, starving follow-up/recovery logic."""
    res = fallback(
        safe_answer="It is a thing that helps the database work better somehow.",
        expected_concepts=["B+ tree"],
        topic="Database Indexing",
        question_type="technical",
        question_text="Explain database indexing.",
    )
    for key in ("misconceptions", "recommended_action", "missing_concepts",
                "answer_quality", "demonstrated_concepts", "difficulty_demonstrated",
                "overall_question_score", "evidence", "feedback_text"):
        assert key in res, f"{key} missing from deterministic fallback"


@pytest.mark.asyncio
async def test_h5_provider_failure_persists_the_deterministic_fallback(api_client, monkeypatch):
    """evaluate_answer() raising must persist the evaluator's fallback, not 5.2."""
    client, (company_id, role_id) = api_client
    headers = await _authenticate(client)

    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "mode": "text",
        "interview_type": "technical", "duration_minutes": 30,
    })
    assert created.status_code == 200, created.text
    interview_id = created.json()["id"]
    question = created.json()["current_question"]

    answer_text = "It is a thing that helps the database work better somehow."
    expected = fallback(
        safe_answer=answer_text,
        expected_concepts=question.get("expected_concepts") or [],
        topic=question["topic"],
        question_type=question.get("question_type") or "technical",
        question_text=question["question_text"],
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated provider construction failure")

    monkeypatch.setattr(AnswerEvaluator, "evaluate_answer", staticmethod(_boom))

    submitted = await client.post(
        f"/api/v1/interviews/{interview_id}/answer", headers=headers,
        json={"answer_text": answer_text},
    )
    assert submitted.status_code == 200, submitted.text

    stored = submitted.json()["evaluation"]
    persisted = (
        stored["correctness_score"], stored["relevance_score"],
        stored["reasoning_score"], stored["depth_score"],
        stored["communication_score"],
    )
    assert persisted != FABRICATED, "fabricated passing rubric was stored"
    assert stored["overall_question_score"] != FABRICATED_OVERALL
    assert persisted == rubric(expected), "stored scores diverge from the evaluator fallback"
    assert stored["overall_question_score"] == expected["overall_question_score"]


@pytest.mark.asyncio
async def test_h5_unrecoverable_failure_stores_no_evaluation(api_client, monkeypatch):
    """If the fallback itself fails, no score is invented."""
    client, (company_id, role_id) = api_client
    headers = await _authenticate(client)

    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "mode": "text",
        "interview_type": "technical", "duration_minutes": 30,
    })
    assert created.status_code == 200, created.text
    interview_id = created.json()["id"]

    async def _boom(*args, **kwargs):
        raise RuntimeError("primary evaluation failure")

    def _boom_sync(*args, **kwargs):
        raise RuntimeError("fallback failure")

    monkeypatch.setattr(AnswerEvaluator, "evaluate_answer", staticmethod(_boom))
    monkeypatch.setattr(
        AnswerEvaluator, "_deterministic_fallback_evaluation", staticmethod(_boom_sync)
    )

    submitted = await client.post(
        f"/api/v1/interviews/{interview_id}/answer", headers=headers,
        json={"answer_text": "Some answer that cannot be evaluated."},
    )
    assert submitted.status_code == 503
    detail = submitted.json()["detail"]
    assert "evaluation is temporarily unavailable" in detail
    # Internal exception text must not leak to the client.
    assert "RuntimeError" not in detail
    assert "fallback failure" not in detail


@pytest.mark.asyncio
async def test_h5_successful_evaluation_flow_is_unchanged(api_client):
    """The normal path still stores a real evaluation and returns the contract."""
    client, (company_id, role_id) = api_client
    headers = await _authenticate(client)

    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "mode": "text",
        "interview_type": "technical", "duration_minutes": 30,
    })
    assert created.status_code == 200, created.text
    interview_id = created.json()["id"]

    # A genuinely successful evaluation (no failure injected). See the note in
    # test_h2_state_persists_through_the_real_answer_endpoint for why this
    # particular answer is used.
    submitted = await client.post(
        f"/api/v1/interviews/{interview_id}/answer", headers=headers,
        json={"answer_text": "It is a thing that helps the database work better somehow."},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()

    assert "evaluation" in body and "interview_state" in body
    evaluation = body["evaluation"]
    for key in ("correctness_score", "relevance_score", "reasoning_score",
                "depth_score", "communication_score", "overall_question_score"):
        assert key in evaluation
        assert 0.0 <= evaluation[key] <= 10.0


# ======================================================================
# R1 - refusal detection must not fire on ordinary technical vocabulary
# ======================================================================

VALID_TECHNICAL_ANSWERS = [
    "Passwords are hashed with bcrypt and a per-user salt before being stored.",
    "In Python, arguments are passed by object reference, so mutating a list "
    "inside a function is visible to the caller.",
    "A skip list is a probabilistic data structure that layers linked lists to "
    "give O(log n) search.",
    "The request passes through the authentication middleware before reaching "
    "the handler.",
    "We used a bypass cache for hot keys to reduce database load.",
    "You can skip the rebalancing step when the tree is already height-balanced.",
]

GENUINE_REFUSALS = [
    "I don't know", "i dont know", "no idea", "No clue.", "not familiar",
    "I have no idea", "unsure", "pass", "skip", "Pass.", "  SKIP  ",
    # A refusal that explains itself is still a refusal.
    "I don't know, I haven't done any projects.",
]


@pytest.mark.parametrize("answer", VALID_TECHNICAL_ANSWERS)
def test_r1_valid_technical_answer_is_not_a_refusal(answer):
    """These contain "pass"/"skip" only as ordinary vocabulary."""
    assert is_explicit_unknown(answer) is False
    state = classify_response_quality_state(
        safe_answer=answer,
        topic="Password Storage",
        expected_concepts=["hashing", "salt"],
        question_type="technical",
        question_text="Explain how passwords should be stored.",
    )
    assert state != "EXPLICIT_UNKNOWN"


@pytest.mark.parametrize("answer", GENUINE_REFUSALS)
def test_r1_genuine_refusal_is_still_detected(answer):
    """The fix must not cost any real refusal detection."""
    assert is_explicit_unknown(answer) is True


@pytest.mark.asyncio
async def test_r1_valid_answer_is_not_short_circuited_to_zero():
    """EXPLICIT_UNKNOWN returns 0.0 without calling the LLM; a valid answer must not.

    This is the production consequence: a correct answer scored 0.0 drives the
    engine's knowledge-floor check and can conclude the interview early.
    """
    result = await AnswerEvaluator.evaluate_answer(
        candidate_answer=VALID_TECHNICAL_ANSWERS[0],
        question_text="Explain how passwords should be stored.",
        topic="Password Storage",
        expected_concepts=["hashing", "salt"],
        question_type="technical",
    )
    assert result["overall_question_score"] > 0.0
    assert result["answer_quality"] != "unknown"
    assert result["recommended_action"] != "recover"


@pytest.mark.asyncio
async def test_r1_explicit_refusal_still_scores_zero_and_recovers():
    """The genuine refusal path is unchanged."""
    result = await AnswerEvaluator.evaluate_answer(
        candidate_answer="I don't know",
        question_text="Explain how passwords should be stored.",
        topic="Password Storage",
        expected_concepts=["hashing", "salt"],
        question_type="technical",
    )
    assert result["correctness_score"] == 0.0
    assert result["answer_quality"] == "unknown"
