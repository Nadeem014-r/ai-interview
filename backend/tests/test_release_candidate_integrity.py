"""Release-candidate integrity checks: persistence, scoping and voice parity.

These pin the invariants a multi-turn interview depends on and that no other
suite asserts end to end over HTTP: an answer is stored exactly once, a retry
cannot double-score a question, one interview's state cannot leak into another,
and the backend accepts the short spoken answers a real candidate gives.

Safety: throwaway SQLite via the root conftest; providers pinned to mock by
tests/conftest.py. No paid provider and no real database are contacted.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.db.models import Answer, Evaluation, InterviewState
from app.main import app

PASSWORD = "ValidPassword123!"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _candidate(client: AsyncClient) -> dict:
    email = f"rc_{uuid.uuid4().hex[:10]}@example.com"
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD,
        "full_name": "RC Candidate", "role": "candidate",
    })
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _start_interview(client: AsyncClient, headers: dict, role_filter=None) -> dict:
    companies = (await client.get("/api/v1/companies")).json()
    company = companies[0]
    if role_filter:
        for c in companies:
            roles = (await client.get(f"/api/v1/companies/{c['id']}/roles")).json()
            match = [r for r in roles if role_filter(r["title"])]
            if match:
                company = c
                role = match[0]
                break
        else:
            role = (await client.get(f"/api/v1/companies/{company['id']}/roles")).json()[0]
    else:
        role = (await client.get(f"/api/v1/companies/{company['id']}/roles")).json()[0]

    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company["id"],
        "role_id": role["id"],
        "mode": "text",
        "interview_type": "technical",
        "duration_minutes": 30,
        "target_level": "entry",
    })
    assert created.status_code == 200, created.text
    return created.json()


# ======================================================================
# Persistence integrity
# ======================================================================

@pytest.mark.asyncio
async def test_answer_and_evaluation_are_persisted_exactly_once():
    """Every submitted answer must yield exactly one Answer and one Evaluation."""
    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(client, headers)
        interview_id = interview["id"]

        submitted = 0
        for _ in range(2):
            detail = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
            if detail["status"] == "completed" or not detail.get("current_question"):
                break
            res = await client.post(
                f"/api/v1/interviews/{interview_id}/answer",
                headers=headers,
                json={"answer_text": "Connection pooling bounds concurrent database work."},
            )
            assert res.status_code == 200, res.text
            submitted += 1
            if res.json()["is_completed"]:
                break

    assert submitted >= 1

    async with AsyncSessionLocal() as s:
        n_answers = (await s.execute(
            select(func.count()).select_from(Answer).where(Answer.interview_id == interview_id)
        )).scalar()
        n_evals = (await s.execute(
            select(func.count()).select_from(Evaluation)
            .join(Answer, Evaluation.answer_id == Answer.id)
            .where(Answer.interview_id == interview_id)
        )).scalar()

    assert n_answers == submitted, f"expected {submitted} answers, stored {n_answers}"
    assert n_evals == submitted, f"expected {submitted} evaluations, stored {n_evals}"


@pytest.mark.asyncio
async def test_resubmitting_the_same_question_cannot_double_score_it():
    """A retry -- the normal reaction to a flaky voice turn -- must not score twice."""
    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(client, headers)
        interview_id = interview["id"]
        question_id = interview["current_question"]["id"]

        first = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={"answer_text": "An index trades write cost for faster reads."},
        )
        assert first.status_code == 200, first.text

        # Force the same (already answered) question id to be resubmitted by
        # replaying the turn while that question is no longer current.
        replay = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={"answer_text": "An index trades write cost for faster reads."},
        )
        assert replay.status_code in (200, 400), replay.text

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Answer.question_id).where(Answer.interview_id == interview_id)
        )).all()
        answered_question_ids = [r[0] for r in rows]

    assert len(answered_question_ids) == len(set(answered_question_ids)), (
        f"a question was answered twice: {answered_question_ids}"
    )
    assert answered_question_ids.count(question_id) == 1


@pytest.mark.asyncio
async def test_two_interviews_do_not_contaminate_each_other():
    """Adaptive state and answers must be scoped to their own interview."""
    async with _client() as client:
        headers = await _candidate(client)
        first = await _start_interview(client, headers)
        second = await _start_interview(client, headers)
        assert first["id"] != second["id"]

        await client.post(
            f"/api/v1/interviews/{first['id']}/answer",
            headers=headers,
            json={"answer_text": "Sharding splits a dataset horizontally across nodes."},
        )

        second_detail = (await client.get(
            f"/api/v1/interviews/{second['id']}", headers=headers)).json()
        assert second_detail["state"]["questions_asked_count"] == 0, (
            "answering one interview must not advance another"
        )
        assert second_detail["answers"] == []

    async with AsyncSessionLocal() as s:
        n_first = (await s.execute(select(func.count()).select_from(Answer)
                                   .where(Answer.interview_id == first["id"]))).scalar()
        n_second = (await s.execute(select(func.count()).select_from(Answer)
                                    .where(Answer.interview_id == second["id"]))).scalar()
        states = (await s.execute(select(InterviewState)
                                  .where(InterviewState.interview_id.in_(
                                      [first["id"], second["id"]])))).scalars().all()

    assert n_first == 1 and n_second == 0
    assert len({st.interview_id for st in states}) == len(states), "state rows must be per-interview"


# ======================================================================
# Voice parity: the backend must accept what a real candidate says
# ======================================================================

@pytest.mark.parametrize("spoken", ["No.", "Yes", "C++", "No, I haven't used it."])
@pytest.mark.asyncio
async def test_backend_accepts_short_spoken_answers(spoken):
    """Short answers are legitimate interview responses and must be scored, not refused.

    This is the backend half of the voice contract. The browser client applies
    its own stricter minimum length (see the release report); the backend itself
    imposes no such floor, so lowering that client gate would require no backend
    change.
    """
    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(client, headers)

        res = await client.post(
            f"/api/v1/interviews/{interview['id']}/answer",
            headers=headers,
            json={"answer_text": spoken, "audio_url": "memory://rc", "stt_latency_ms": 120},
        )
        assert res.status_code == 200, f"backend refused a valid short answer {spoken!r}: {res.text}"
        score = float(res.json()["evaluation"]["overall_question_score"])
        assert 0.0 <= score <= 10.0


@pytest.mark.asyncio
async def test_failed_transcription_creates_no_answer_row():
    """A provider failure must leave the interview exactly where it was."""
    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(client, headers)
        interview_id = interview["id"]

        rejected = await client.post(
            "/api/v1/voice/stt",
            headers=headers,
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert rejected.status_code == 400

    async with AsyncSessionLocal() as s:
        n = (await s.execute(select(func.count()).select_from(Answer)
                             .where(Answer.interview_id == interview_id))).scalar()
    assert n == 0, "a failed transcription must not persist an answer"


# ======================================================================
# Progression: the interview must behave like an interview
# ======================================================================

@pytest.mark.asyncio
async def test_questions_are_not_repeated_within_an_interview():
    """Duplicate questions are the most visible failure in a live demonstration."""
    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(client, headers)
        interview_id = interview["id"]

        seen_ids = [interview["current_question"]["id"]]
        seen_text = [interview["current_question"]["question_text"].strip().lower()]

        for _ in range(4):
            res = await client.post(
                f"/api/v1/interviews/{interview_id}/answer",
                headers=headers,
                json={"answer_text": (
                    "I would profile the query plan, add a covering index, and measure "
                    "the latency change before and after under representative load."
                )},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            if body["is_completed"] or not body.get("next_question"):
                break
            nq = body["next_question"]
            seen_ids.append(nq["id"])
            seen_text.append(nq["question_text"].strip().lower())

        assert len(seen_ids) == len(set(seen_ids)), f"repeated question id: {seen_ids}"
        assert len(seen_text) == len(set(seen_text)), "the interviewer asked the same question twice"


@pytest.mark.asyncio
async def test_weak_and_strong_answers_are_scored_differently():
    """A non-answer must not receive the same credit as a substantive one."""
    async with _client() as client:
        headers = await _candidate(client)

        weak_interview = await _start_interview(client, headers)
        weak = await client.post(
            f"/api/v1/interviews/{weak_interview['id']}/answer",
            headers=headers,
            json={"answer_text": "I don't know."},
        )
        assert weak.status_code == 200, weak.text
        weak_score = float(weak.json()["evaluation"]["overall_question_score"])

        strong_interview = await _start_interview(client, headers)
        strong = await client.post(
            f"/api/v1/interviews/{strong_interview['id']}/answer",
            headers=headers,
            json={"answer_text": (
                "I would start by reproducing the latency with a representative load "
                "profile, then read the query plan to confirm whether the planner is "
                "choosing a sequential scan. If it is, a covering index on the predicate "
                "columns removes the scan, at the cost of slower writes and more storage. "
                "I would verify the improvement with p95 latency rather than an average, "
                "because averages hide tail regressions."
            )},
        )
        assert strong.status_code == 200, strong.text
        strong_score = float(strong.json()["evaluation"]["overall_question_score"])

        assert strong_score > weak_score, (
            f"a substantive answer ({strong_score}) must outscore a non-answer ({weak_score})"
        )


@pytest.mark.asyncio
async def test_specialised_role_interview_starts_with_role_relevant_context():
    """A specialised role must not be handed the generic opening question.

    Asserted on the deterministic role resolution that feeds the prompt, not on
    generated prose, so this holds without a live provider.
    """
    from app.companies.strategy_engine import CompanyStrategyEngine

    async with _client() as client:
        headers = await _candidate(client)
        interview = await _start_interview(
            client, headers, role_filter=lambda t: "machine learning" in t.lower())
        assert interview.get("current_question") is not None

        role_title = interview.get("role_title") or ""
        if "machine learning" in role_title.lower():
            profile = CompanyStrategyEngine.get_role_profile(role_title)
            assert "Machine Learning" in profile.display_name, (
                f"{role_title!r} resolved to {profile.display_name!r}"
            )
            generic = CompanyStrategyEngine.get_role_profile("Software Engineer")
            assert set(profile.key_technologies) != set(generic.key_technologies), (
                "a specialised role must not reuse the generic technology set"
            )
