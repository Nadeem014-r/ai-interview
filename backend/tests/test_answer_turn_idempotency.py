"""Regression cover for duplicate and interrupted answer turns.

A turn is several commits: the answer, its evaluation, the adaptive state, the
next question. Two failures lived in the gap between them.

1. An answer committed without its evaluation (a restart, a dropped connection,
   a failure inside the engine) left the candidate permanently stuck: the
   duplicate guard rejected every retry with 400 while the state still pointed
   at that same question, so the interview could never be continued.
2. Two submissions that overlapped both read "not answered yet" and both wrote,
   duplicating answers and evaluations and advancing two turns for one answer.
"""

import asyncio
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from app.core.database import AsyncSessionLocal, init_db
from app.db.models import Answer, Evaluation, Interview
from app.main import app


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60.0)


async def _register(client):
    email = f"turn_{uuid.uuid4().hex[:10]}@example.com"
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Str0ng!Passw0rd123", "full_name": "Turn Tester"
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _start_interview(client, headers):
    companies = (await client.get("/api/v1/companies")).json()
    company = next(c for c in companies if "Google" in c["name"])
    roles = (await client.get(f"/api/v1/companies/{company['id']}/roles")).json()
    res = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company["id"], "role_id": roles[0]["id"],
        "mode": "text", "interview_type": "technical", "duration_minutes": 30,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    return body["id"], body["current_question"]


async def _stored(interview_id):
    """Answers stored for an interview, and how many evaluations they carry."""
    async with AsyncSessionLocal() as db:
        answers = (await db.execute(
            select(Answer).where(Answer.interview_id == interview_id)
        )).scalars().all()
        evals = (await db.execute(
            select(func.count()).select_from(Evaluation)
            .where(Evaluation.answer_id.in_([a.id for a in answers] or [0]))
        )).scalar_one()
    return answers, evals


@pytest.mark.asyncio
async def test_interrupted_turn_is_resumed_not_rejected():
    """An answer stored without an evaluation must be completable, not fatal."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question = await _start_interview(client, headers)

        # A turn that committed its answer and then died before scoring it.
        async with AsyncSessionLocal() as db:
            db.add(Answer(
                interview_id=interview_id, question_id=question["id"],
                candidate_answer_text="answer stored before the crash", stt_latency_ms=0,
            ))
            await db.commit()

        res = await client.post(
            f"/api/v1/interviews/{interview_id}/answer", headers=headers,
            json={"answer_text": "answer stored before the crash", "question_id": question["id"]},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["evaluation"]["overall_question_score"] is not None
        # The interview moved on rather than staying on the stranded question.
        assert body["is_completed"] or body["next_question"]["id"] != question["id"]

        answers, evals = await _stored(interview_id)
        assert len(answers) == 1, "resuming must reuse the stored answer, not add a second"
        assert evals == 1, "resuming must score the stored answer exactly once"
        # The candidate's own words are what got scored.
        assert answers[0].candidate_answer_text == "answer stored before the crash"


@pytest.mark.asyncio
async def test_retry_of_a_scored_turn_replays_it():
    """Re-sending a scored turn returns the same result and writes nothing."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question = await _start_interview(client, headers)
        payload = {
            "answer_text": "I build backend services in Python and care about databases.",
            "question_id": question["id"],
        }

        first = (await client.post(f"/api/v1/interviews/{interview_id}/answer",
                                   headers=headers, json=payload)).json()
        answers_before, evals_before = await _stored(interview_id)

        retry = await client.post(f"/api/v1/interviews/{interview_id}/answer",
                                  headers=headers, json=payload)
        assert retry.status_code == 200, retry.text
        replay = retry.json()

        assert replay["evaluation"]["overall_question_score"] == \
            first["evaluation"]["overall_question_score"]
        assert replay["next_question"]["id"] == first["next_question"]["id"], \
            "a retry must not consume a second question"

        answers_after, evals_after = await _stored(interview_id)
        assert len(answers_after) == len(answers_before) == 1
        assert evals_after == evals_before == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_submissions_advance_one_turn():
    """Overlapping submissions of one answer must not double-write or double-advance."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question = await _start_interview(client, headers)
        payload = {
            "answer_text": "A B-tree index keeps keys sorted so lookups avoid a full scan.",
            "question_id": question["id"],
        }

        results = await asyncio.gather(*[
            client.post(f"/api/v1/interviews/{interview_id}/answer", headers=headers, json=payload)
            for _ in range(4)
        ])
        assert all(r.status_code == 200 for r in results), [r.status_code for r in results]

        answers, evals = await _stored(interview_id)
        assert len(answers) == 1, f"one submission must store one answer, stored {len(answers)}"
        assert evals == 1, f"one submission must store one evaluation, stored {evals}"

        # Every response describes the same single turn.
        next_ids = {r.json()["next_question"]["id"] for r in results if r.json().get("next_question")}
        assert len(next_ids) <= 1, f"concurrent submits advanced to different questions: {next_ids}"

        async with AsyncSessionLocal() as db:
            interview = (await db.execute(
                select(Interview).where(Interview.id == interview_id)
            )).scalars().first()
            await db.refresh(interview, ["state"])
            assert interview.state.questions_asked_count == len(answers), \
                "state counter drifted from the stored answers"


@pytest.mark.asyncio
async def test_legacy_client_without_question_id_does_not_burn_two_questions():
    """Older clients omit question_id; a double submit must still count once."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, _ = await _start_interview(client, headers)
        payload = {"answer_text": "Redis caches the listing endpoint with a five minute TTL."}

        results = await asyncio.gather(*[
            client.post(f"/api/v1/interviews/{interview_id}/answer", headers=headers, json=payload)
            for _ in range(3)
        ])
        assert all(r.status_code == 200 for r in results), [r.status_code for r in results]
        answers, evals = await _stored(interview_id)
        assert len(answers) == 1, f"stored {len(answers)} answers for one submission"
        assert evals == 1


@pytest.mark.asyncio
async def test_normal_sequential_flow_is_unchanged():
    """Distinct answers to successive questions still each count as their own turn."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question = await _start_interview(client, headers)

        texts = [
            "I am a final year CS student who built a FastAPI event portal backed by Postgres.",
            "A B-tree index stores keys in sorted order, so lookups are O(log n) instead of a scan.",
            "I would shard by user id with consistent hashing and keep one read replica per shard.",
        ]
        asked, current = [], question
        for text in texts:
            asked.append(current["id"])
            res = await client.post(f"/api/v1/interviews/{interview_id}/answer", headers=headers,
                                    json={"answer_text": text, "question_id": current["id"]})
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["evaluation"]["overall_question_score"] is not None
            if body["is_completed"] or not body.get("next_question"):
                break
            current = body["next_question"]

        answers, evals = await _stored(interview_id)
        assert len(answers) == len(asked) == len(set(asked)), "each turn stores its own answer"
        assert evals == len(answers), "each answer keeps exactly one evaluation"

        # Ownership is still enforced on the same endpoint.
        other = await _register(client)
        blocked = await client.post(f"/api/v1/interviews/{interview_id}/answer", headers=other,
                                    json={"answer_text": "not mine"})
        assert blocked.status_code == 403

        empty = await client.post(f"/api/v1/interviews/{interview_id}/answer", headers=headers,
                                  json={"answer_text": "   "})
        assert empty.status_code == 400
