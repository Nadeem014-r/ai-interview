"""The answer turn only pre-synthesises interviewer audio that will be played.

Text mode speaks nothing, and a coding turn replaces the voice and video rooms
with the editor. Pre-synthesising the next question in either case spent a
bounded Kokoro slot on 10-25 s of CPU per turn for audio nobody requests.

Reuses the throwaway-SQLite API fixtures from the H1/H2/H5 regression module,
so nothing here touches the configured database.
"""

import pytest

from app.api.v1 import interviews as interviews_api
from app.db.models import Question
from app.evaluation.evaluator import AnswerEvaluator
from app.interview.engine import AdaptiveInterviewEngine
from tests.test_audit_h1_h2_h5_regression import (  # noqa: F401  (fixtures)
    _authenticate,
    api_client,
    sqlite_sessionmaker,
)


async def _run_turn(client, company_id, role_id, monkeypatch, mode, next_type):
    headers = await _authenticate(client)
    created = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id, "mode": mode,
        "interview_type": "technical", "duration_minutes": 30,
    })
    assert created.status_code == 200, created.text
    interview_id = created.json()["id"]

    prefetched: list[str] = []
    monkeypatch.setattr(interviews_api, "_prefetch_question_audio", prefetched.append)

    async def _eval(**kwargs):
        return AnswerEvaluator._deterministic_fallback_evaluation(
            safe_answer=kwargs["candidate_answer"],
            expected_concepts=kwargs["expected_concepts"],
            topic=kwargs["topic"],
            question_type=kwargs["question_type"],
            question_text=kwargs["question_text"],
        )

    monkeypatch.setattr(AnswerEvaluator, "evaluate_answer", staticmethod(_eval))

    next_q = Question(
        id=987654,
        topic="Algorithms",
        difficulty="medium",
        question_type=next_type,
        question_text=f"Next {next_type} question for {mode} mode?",
        expected_concepts=[],
        follow_ups=[],
    )

    async def _progress(self, interview, state, **kwargs):
        return state, next_q, False

    monkeypatch.setattr(AdaptiveInterviewEngine, "process_answer_turn", _progress)

    submitted = await client.post(
        f"/api/v1/interviews/{interview_id}/answer", headers=headers,
        json={"answer_text": "A hash map counts occurrences in one linear pass."},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["next_question"]["question_text"] == next_q.question_text
    return prefetched, next_q.question_text


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,next_type,expect_prefetch", [
    ("text", "technical", False),
    ("audio", "technical", True),
    ("video", "technical", True),
    ("audio", "coding", False),
    ("video", "coding", False),
])
async def test_next_question_prefetch_follows_mode_and_turn_type(
    api_client, monkeypatch, mode, next_type, expect_prefetch
):
    client, (company_id, role_id) = api_client
    prefetched, question_text = await _run_turn(
        client, company_id, role_id, monkeypatch, mode, next_type
    )

    if expect_prefetch:
        assert len(prefetched) == 1
        # Video speaks the bare question; audio may prefix the reaction.
        assert prefetched[0].endswith(question_text)
    else:
        assert prefetched == [], f"{mode}/{next_type} synthesised audio nobody plays"
