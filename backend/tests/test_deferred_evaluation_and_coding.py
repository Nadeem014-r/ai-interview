"""Regression tests for the deferred-evaluation interview flow.

What is pinned here:

1. During a running interview the candidate is served their own answers and no
   assessment of them. The evaluations are still computed and persisted on every
   turn -- the adaptive engine steers on them -- and are released once the
   session is over, so nothing is lost, only deferred.
2. Finishing is idempotent. A double click, a retried request or a second tab
   produce one completion and one report, never two.
3. Report status is answered from the stored report, so it survives a refresh, a
   new tab or a different device, and it self-heals if generation was lost.
4. A coding exercise is offered only when the interview type, the role and the
   candidate's own background all agree -- never from a single resume keyword --
   and its provenance is stated honestly.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, init_db
from app.db.models import Answer, Evaluation, Interview, Question, Report
from app.main import app
from app.interview.coding_selector import (
    MIN_QUESTIONS_BEFORE_CODING,
    MIN_SECONDS_REMAINING_FOR_CODING,
    build_coding_question,
    is_coding_eligible,
)


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=60.0)


async def _register(client):
    email = f"defer_{uuid.uuid4().hex[:10]}@example.com"
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Str0ng!Passw0rd123", "full_name": "Defer Tester"
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── Coding eligibility ───────────────────────────────────────────────────────

_ELIGIBLE = dict(
    interview_type="technical",
    role_title="Backend Software Engineer",
    required_skills=["Java", "Data Structures"],
    role_key_topics=["Algorithms"],
    candidate_skills=["Java", "Spring Boot"],
    questions_asked_count=5,
    time_remaining_seconds=900,
    interview_stage="core",
    already_asked=False,
)


def test_eligible_when_everything_agrees():
    eligible, reason = is_coding_eligible(**_ELIGIBLE)
    assert eligible, reason


def test_hr_interview_never_gets_coding():
    eligible, reason = is_coding_eligible(**{**_ELIGIBLE, "interview_type": "hr"})
    assert not eligible and reason == "interview_type_excludes_coding"


def test_non_coding_role_never_gets_coding():
    """A single language on a resume is not enough: the role has to want code."""
    eligible, reason = is_coding_eligible(
        **{
            **_ELIGIBLE,
            "role_title": "Technical Program Manager",
            "required_skills": ["Roadmapping", "Stakeholder management"],
            "role_key_topics": ["Delivery"],
            "candidate_skills": ["Java"],
        }
    )
    assert not eligible and reason == "role_does_not_require_coding"


def test_engineering_manager_is_not_a_coding_role():
    eligible, _ = is_coding_eligible(**{**_ELIGIBLE, "role_title": "Engineering Manager"})
    assert not eligible


def test_no_programming_background_blocks_coding():
    eligible, reason = is_coding_eligible(
        **{
            **_ELIGIBLE,
            "candidate_skills": ["Excel", "Jira", "Figma"],
            "role_key_topics": ["Communication"],
        }
    )
    assert not eligible and reason == "no_programming_background_evidence"


def test_not_offered_before_the_interview_settles():
    eligible, reason = is_coding_eligible(
        **{**_ELIGIBLE, "questions_asked_count": MIN_QUESTIONS_BEFORE_CODING - 1}
    )
    assert not eligible and reason == "too_early_in_interview"


def test_not_offered_without_time_to_write_it():
    eligible, reason = is_coding_eligible(
        **{**_ELIGIBLE, "time_remaining_seconds": MIN_SECONDS_REMAINING_FOR_CODING - 1}
    )
    assert not eligible and reason == "insufficient_time_remaining"


def test_never_offered_twice():
    eligible, reason = is_coding_eligible(**{**_ELIGIBLE, "already_asked": True})
    assert not eligible and reason == "coding_already_asked"


def test_recovery_is_not_interrupted_by_coding():
    eligible, reason = is_coding_eligible(**{**_ELIGIBLE, "interview_stage": "recovery"})
    assert not eligible and reason == "stage_excludes_coding"


def test_provenance_is_not_falsely_attributed():
    """The platform holds no verified record of a company's real questions, so
    it must not claim one was asked by that company."""
    data = build_coding_question(
        topic="Algorithms",
        difficulty="medium",
        company_name="Acme Corp",
        role_title="Backend Engineer",
        candidate_skills=["C++"],
    )
    text = data["question_text"]
    assert text.startswith("Interview-style coding question relevant to")
    assert "Acme Corp" in text
    lowered = text.lower()
    for false_claim in ("asked by", "was asked at", "actual question from"):
        assert false_claim not in lowered
    assert data["question_type"] == "coding"
    assert data["suggested_language"] == "C++"


# ── Deferred evaluation, finish idempotency, report status ───────────────────


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
    return body["id"], body["current_question"], company["id"], roles[0]["id"]


@pytest.mark.asyncio
async def test_active_interview_withholds_evaluation_but_persists_it():
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)

        res = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={
                "answer_text": "A hash map hashes the key to a bucket, giving average constant time lookup.",
                "question_id": question["id"],
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text

        # The candidate's own view of the running session carries the answer and
        # no assessment of it.
        session = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
        assert session["status"] != "completed"
        assert len(session["answers"]) >= 1
        for turn in session["answers"]:
            assert turn.get("evaluation") is None, "score/feedback leaked mid-interview"

    # It was still computed and stored, which is what the adaptive engine reads.
    async with AsyncSessionLocal() as db:
        stored = (await db.execute(
            select(Evaluation).join(Answer).where(Answer.interview_id == interview_id)
        )).scalars().all()
    assert len(stored) >= 1
    assert stored[0].feedback_text


@pytest.mark.asyncio
async def test_history_listing_also_withholds_evaluation_while_active():
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)
        await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "Indexes trade write cost for read speed.", "question_id": question["id"]},
            headers=headers,
        )

        history = (await client.get("/api/v1/interviews/history", headers=headers)).json()
        active = [i for i in history if i["id"] == interview_id]
        assert active, "the running interview is missing from history"
        for turn in active[0].get("answers") or []:
            assert turn.get("evaluation") is None


@pytest.mark.asyncio
async def test_completed_interview_releases_full_detail():
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)
        await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "Indexes trade write cost for read speed.", "question_id": question["id"]},
            headers=headers,
        )
        await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)

        session = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
        assert session["status"] == "completed"
        assert any(t.get("evaluation") for t in session["answers"]), "detail lost after completion"


@pytest.mark.asyncio
async def test_finish_is_idempotent():
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)
        await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "Normalisation removes redundancy.", "question_id": question["id"]},
            headers=headers,
        )

        for _ in range(3):
            res = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
            assert res.status_code == 200, res.text

        # Drain the detached report generation before counting.
        for _ in range(30):
            status = (await client.get(
                f"/api/v1/interviews/{interview_id}/report-status", headers=headers
            )).json()
            if status["status"] == "ready":
                break

    async with AsyncSessionLocal() as db:
        reports = (await db.execute(
            select(Report).where(Report.interview_id == interview_id)
        )).scalars().all()
        interview = (await db.execute(
            select(Interview).where(Interview.id == interview_id)
        )).scalars().first()
    assert len(reports) <= 1, "a retried finish produced a second report"
    assert interview.status == "completed"


@pytest.mark.asyncio
async def test_report_status_survives_navigation():
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)
        await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "A deadlock needs mutual exclusion and circular wait.",
                  "question_id": question["id"]},
            headers=headers,
        )

        before = await client.get(f"/api/v1/interviews/{interview_id}/report-status", headers=headers)
        assert before.status_code == 200
        assert before.json()["status"] == "in_progress"

        await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)

        # Answered from the database, so asking again from anywhere gives the
        # same answer without redoing any work.
        for _ in range(3):
            status = await client.get(
                f"/api/v1/interviews/{interview_id}/report-status", headers=headers
            )
            assert status.status_code == 200
            assert status.json()["status"] in ("processing", "ready")


@pytest.mark.asyncio
async def test_report_status_rejects_another_candidate():
    await init_db()
    async with _client() as client:
        owner = await _register(client)
        interview_id, _, _, _ = await _start_interview(client, owner)
        intruder = await _register(client)
        res = await client.get(f"/api/v1/interviews/{interview_id}/report-status", headers=intruder)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_answer_turn_still_replays_a_duplicate_submission():
    """Batch 6 idempotency is untouched: the same question answered twice stores
    one answer and one evaluation."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, question, _, _ = await _start_interview(client, headers)

        body = {"answer_text": "Threads share an address space; processes do not.",
                "question_id": question["id"]}
        first = await client.post(f"/api/v1/interviews/{interview_id}/answer", json=body, headers=headers)
        second = await client.post(f"/api/v1/interviews/{interview_id}/answer", json=body, headers=headers)
        assert first.status_code == second.status_code == 200

    async with AsyncSessionLocal() as db:
        answers = (await db.execute(
            select(Answer).where(Answer.interview_id == interview_id,
                                 Answer.question_id == question["id"])
        )).scalars().all()
        assert len(answers) == 1
        evaluations = (await db.execute(
            select(Evaluation).where(Evaluation.answer_id == answers[0].id)
        )).scalars().all()
        assert len(evaluations) == 1


@pytest.mark.asyncio
async def test_a_coding_turn_uses_the_same_answer_endpoint():
    """The coding workspace submits through the ordinary answer turn, so it
    inherits ownership checks, idempotency and adaptive progression rather than
    needing a second path of its own."""
    await init_db()
    async with _client() as client:
        headers = await _register(client)
        interview_id, _, company_id, role_id = await _start_interview(client, headers)

        async with AsyncSessionLocal() as db:
            coding_q = Question(
                company_id=company_id,
                role_id=role_id,
                topic="Algorithms",
                difficulty="medium",
                question_type="coding",
                question_text="Interview-style coding question relevant to this role.",
                expected_concepts=["Sliding window"],
                follow_ups=[],
            )
            db.add(coding_q)
            await db.commit()
            await db.refresh(coding_q)
            coding_q_id = coding_q.id

        submission = "Language: C++\n\nint main() { return 0; }"
        first = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": submission, "question_id": coding_q_id},
            headers=headers,
        )
        assert first.status_code == 200, first.text

        # A refresh or a double click must not produce a second submission.
        second = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "Language: C++\n\n// different code", "question_id": coding_q_id},
            headers=headers,
        )
        assert second.status_code == 200

    async with AsyncSessionLocal() as db:
        stored = (await db.execute(
            select(Answer).where(Answer.interview_id == interview_id,
                                 Answer.question_id == coding_q_id)
        )).scalars().all()
    assert len(stored) == 1
    assert stored[0].candidate_answer_text == submission, "the immutable submission was overwritten"
