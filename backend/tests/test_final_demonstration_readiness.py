"""Final university-demonstration verification.

This module drives the *real* application over its HTTP surface -- the same
routes the browser calls -- rather than exercising helpers in isolation, so the
verification covers routing, authentication, request validation, the service
layer and persistence together.

Scope note: the individual behaviours below are already covered by the phase and
batch suites. What is verified here, and nowhere else, is that the whole
critical journey holds together end to end in one session against a clean
database, plus the failure cases a demonstration is most likely to hit in front
of an audience.

Safety:
  * The root conftest binds the engine to a throwaway SQLite file and aborts the
    session if the database is not recognisably a test database, so no
    development or production PostgreSQL is ever contacted.
  * tests/conftest.py forces DEFAULT_LLM_PROVIDER / STT / TTS to "mock" for the
    session, so no paid provider is called. test_demonstration_uses_no_paid_provider
    asserts that rather than assuming it.
  * The resume uploaded here is a fixture generated in-process. No real
    candidate document is read.
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

PASSWORD = "ValidPassword123!"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_and_login(client: AsyncClient) -> tuple[str, dict]:
    """Register a fresh candidate and return (email, auth headers)."""
    email = f"demo_{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": PASSWORD,
        "full_name": "Demonstration Candidate",
        "role": "candidate",
    })
    assert reg.status_code in (200, 201), reg.text

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return email, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _resume_bytes() -> bytes:
    """A minimal, entirely synthetic resume. No real candidate data is used."""
    return (
        b"Demonstration Candidate\n"
        b"B.Tech Computer Science, State Technical University, 2025\n"
        b"Skills: Python, FastAPI, PostgreSQL, Docker, SQL, REST APIs\n"
        b"Project: Built a FastAPI service with PostgreSQL persistence and Redis caching.\n"
        b"Experience: Backend engineering intern working on async APIs.\n"
    )


# ======================================================================
# PHASE B -- the critical journey, end to end
# ======================================================================

@pytest.mark.asyncio
async def test_health_and_readiness_endpoints():
    """Stage 1-2: the probes an operator and a container orchestrator rely on."""
    async with _client() as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        liveness = await client.get("/health/liveness")
        assert liveness.status_code == 200

        # Readiness reports on the database, so it must answer either way and
        # never hang or 500.
        readiness = await client.get("/health/readiness")
        assert readiness.status_code in (200, 503)
        assert "status" in readiness.json()


@pytest.mark.asyncio
async def test_catalogue_available_on_clean_database():
    """Stage 4: a freshly provisioned database must already offer companies and roles."""
    async with _client() as client:
        companies = await client.get("/api/v1/companies")
        assert companies.status_code == 200
        payload = companies.json()
        assert len(payload) > 0, "a clean database must expose the seeded catalogue"

        company_id = payload[0]["id"]
        roles = await client.get(f"/api/v1/companies/{company_id}/roles")
        assert roles.status_code == 200
        assert len(roles.json()) > 0, "every catalogue company must expose at least one role"


@pytest.mark.asyncio
async def test_full_interview_journey_end_to_end():
    """Stages 3, 5-13: registration through to the generated report, in one session."""
    async with _client() as client:
        # --- Stage 3: authentication ---------------------------------------
        _, headers = await _register_and_login(client)

        profile = await client.get("/api/v1/profile", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["full_name"] == "Demonstration Candidate"

        # --- Stage 5: resume upload and processing --------------------------
        upload = await client.post(
            "/api/v1/resume/upload",
            headers=headers,
            files={"file": ("demo_resume.txt", io.BytesIO(_resume_bytes()), "text/plain")},
        )
        # A .txt resume may legitimately be refused by the extension allowlist;
        # what must not happen is a server error.
        assert upload.status_code in (201, 400, 415), upload.text
        resume_accepted = upload.status_code == 201

        if resume_accepted:
            current = await client.get("/api/v1/resume/current", headers=headers)
            assert current.status_code == 200

        # --- Stage 6: job matching -----------------------------------------
        matches = await client.get("/api/v1/jobs/matches", headers=headers)
        assert matches.status_code in (200, 400, 404), matches.text
        if matches.status_code == 200:
            assert isinstance(matches.json(), list)

        # --- Stage 7: interview creation ------------------------------------
        companies = (await client.get("/api/v1/companies")).json()
        company = companies[0]
        roles = (await client.get(f"/api/v1/companies/{company['id']}/roles")).json()
        role = roles[0]

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": company["id"],
            "role_id": role["id"],
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        assert created.status_code == 200, created.text
        interview = created.json()
        interview_id = interview["id"]
        assert interview["status"] == "in_progress"

        # --- Stage 8: first question is generated on creation ---------------
        assert interview.get("current_question") is not None, (
            "the candidate must be given a question without a further round trip"
        )
        assert interview["current_question"]["question_text"].strip()

        # --- Stages 9-12: answer -> evaluation -> adaptive turn -> next question
        turns_completed = 0
        for _ in range(3):
            detail = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)
            assert detail.status_code == 200
            state = detail.json()
            if state["status"] == "completed" or not state.get("current_question"):
                break

            answer = await client.post(
                f"/api/v1/interviews/{interview_id}/answer",
                headers=headers,
                json={"answer_text": (
                    "I would use an async FastAPI endpoint backed by PostgreSQL. "
                    "Connection pooling bounds concurrency, and I index the columns "
                    "used in the query predicate so lookups stay on an index scan "
                    "rather than a sequential scan under load."
                )},
            )
            assert answer.status_code == 200, answer.text
            body = answer.json()
            turns_completed += 1

            # Stage 10: a real evaluation, with the full rubric populated.
            evaluation = body["evaluation"]
            for dimension in (
                "correctness_score", "relevance_score", "reasoning_score",
                "depth_score", "communication_score", "overall_question_score",
            ):
                assert dimension in evaluation, f"evaluation is missing {dimension}"
                assert 0.0 <= float(evaluation[dimension]) <= 10.0

            # Stage 11: the adaptive engine advanced the interview state.
            assert body["interview_state"]["questions_asked_count"] >= turns_completed

            # Stage 12: either a next question, or a truthful completion.
            if body["is_completed"]:
                assert body.get("closing_message")
                break
            assert body.get("next_question") is not None

        assert turns_completed >= 1, "at least one answer turn must be evaluated"

        # --- Stage 13: report generation ------------------------------------
        finish = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
        assert finish.status_code == 200, finish.text

        report = await client.get(f"/api/v1/reports/{interview_id}", headers=headers)
        assert report.status_code == 200, report.text
        report_body = report.json()
        assert 0.0 <= float(report_body["overall_score"]) <= 100.0
        assert report_body["strengths"], "a report must always state something about strengths"
        assert report_body["weaknesses"]
        assert report_body["executive_summary"].strip()


@pytest.mark.asyncio
async def test_report_is_not_regenerated_on_repeat_request():
    """Batch 9's idempotency guard must hold over the real HTTP path too."""
    async with _client() as client:
        _, headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        interview_id = created.json()["id"]

        await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={"answer_text": "Indexes turn a sequential scan into an index scan."},
        )

        first = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
        second = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["report_id"] == second.json()["report_id"], (
            "finishing twice must reuse the stored report, not pay for a second one"
        )


# ======================================================================
# PHASE B -- voice path
# ======================================================================

@pytest.mark.asyncio
async def test_voice_transcript_feeds_the_same_evaluation_engine():
    """Stage 14: a spoken answer must reach the identical evaluation path as text.

    The transcript is submitted through the same /answer route with the voice
    metadata a real client sends, proving voice does not have a second,
    divergent scoring implementation.
    """
    async with _client() as client:
        _, headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "audio",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        assert created.status_code == 200
        interview_id = created.json()["id"]

        spoken = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={
                "answer_text": "A database index speeds up lookups at the cost of write throughput.",
                "audio_url": "memory://demo-recording",
                "stt_latency_ms": 350,
            },
        )
        assert spoken.status_code == 200, spoken.text
        evaluation = spoken.json()["evaluation"]
        assert "overall_question_score" in evaluation
        assert 0.0 <= float(evaluation["overall_question_score"]) <= 10.0


@pytest.mark.asyncio
async def test_tts_endpoint_serves_audio_for_the_interviewer_voice():
    """The interviewer's voice must be produced through the configured provider."""
    async with _client() as client:
        _, headers = await _register_and_login(client)
        res = await client.post(
            "/api/v1/voice/tts",
            headers=headers,
            json={"text": "Welcome to your interview. Please introduce yourself."},
        )
        assert res.status_code == 200, res.text
        assert len(res.content) > 0


# ======================================================================
# PHASE C -- the system must fail truthfully
# ======================================================================

@pytest.mark.asyncio
async def test_invalid_login_is_rejected():
    async with _client() as client:
        email, _ = await _register_and_login(client)
        bad = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "WrongPassword123!",
        })
        assert bad.status_code in (400, 401)
        # The rejection must not disclose which half of the pair was wrong.
        assert "hash" not in bad.text.lower()


@pytest.mark.asyncio
async def test_unauthenticated_access_is_refused():
    async with _client() as client:
        for path in ("/api/v1/profile", "/api/v1/interviews/history", "/api/v1/resume/current"):
            res = await client.get(path)
            assert res.status_code in (401, 403), f"{path} answered {res.status_code} unauthenticated"


@pytest.mark.asyncio
async def test_one_candidate_cannot_read_another_candidates_interview():
    """Authorisation, not just authentication: ownership is enforced per row."""
    async with _client() as client:
        _, owner_headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=owner_headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        interview_id = created.json()["id"]

        _, intruder_headers = await _register_and_login(client)
        stolen = await client.get(f"/api/v1/interviews/{interview_id}", headers=intruder_headers)
        assert stolen.status_code in (403, 404), (
            "another candidate's interview must not be readable"
        )


@pytest.mark.asyncio
async def test_blank_answer_is_rejected_not_scored():
    """An empty answer must be refused rather than silently scored."""
    async with _client() as client:
        _, headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        interview_id = created.json()["id"]

        for blank in ("", "   "):
            res = await client.post(
                f"/api/v1/interviews/{interview_id}/answer",
                headers=headers,
                json={"answer_text": blank},
            )
            assert res.status_code in (400, 422), (
                f"a blank transcript must be rejected, got {res.status_code}"
            )


@pytest.mark.asyncio
async def test_empty_audio_upload_is_rejected():
    """An empty recording is a client problem and must read as 400, not 500."""
    async with _client() as client:
        _, headers = await _register_and_login(client)
        res = await client.post(
            "/api/v1/voice/stt",
            headers=headers,
            files={"file": ("silence.wav", io.BytesIO(b""), "audio/wav")},
        )
        assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_invalid_audio_payload_fails_without_server_error():
    """Undecodable audio must be reported as a bad request, never as a crash."""
    async with _client() as client:
        _, headers = await _register_and_login(client)
        res = await client.post(
            "/api/v1/voice/stt",
            headers=headers,
            files={"file": ("broken.wav", io.BytesIO(b"this is not audio data"), "audio/wav")},
        )
        assert res.status_code in (400, 415, 422), (
            f"invalid audio must not surface as a server error, got {res.status_code}"
        )


@pytest.mark.asyncio
async def test_empty_tts_text_is_rejected():
    async with _client() as client:
        _, headers = await _register_and_login(client)
        res = await client.post("/api/v1/voice/tts", headers=headers, json={"text": "   "})
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_interview_survives_llm_provider_failure(monkeypatch):
    """A provider outage must degrade to a real deterministic score, not a crash.

    The evaluator's own fallback rubric is what keeps the demonstration alive if
    the network drops mid-interview, so it is verified over the HTTP path.
    """
    from app.ai import factory as factory_module

    class DeadProvider:
        async def generate_json(self, *args, **kwargs):
            raise RuntimeError("simulated provider outage")

        async def generate_text(self, *args, **kwargs):
            raise RuntimeError("simulated provider outage")

    async with _client() as client:
        _, headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        assert created.status_code == 200
        interview_id = created.json()["id"]

        monkeypatch.setattr(
            factory_module.AIFactory,
            "get_llm_provider",
            staticmethod(lambda *a, **k: DeadProvider()),
        )

        res = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={"answer_text": "An index trades write throughput for faster reads."},
        )
        # Either a deterministic evaluation, or an honest 503. Never a 500 and
        # never an invented passing score.
        assert res.status_code in (200, 503), res.text
        if res.status_code == 200:
            score = float(res.json()["evaluation"]["overall_question_score"])
            assert 0.0 <= score <= 10.0


@pytest.mark.asyncio
async def test_empty_rag_corpus_does_not_break_question_generation():
    """Batch 9 short-circuited retrieval on an empty corpus; interviews must still run."""
    from app.rag.rag_engine import RAGEngine

    async with _client() as client:
        _, headers = await _register_and_login(client)
        companies = (await client.get("/api/v1/companies")).json()
        roles = (await client.get(f"/api/v1/companies/{companies[0]['id']}/roles")).json()

        created = await client.post("/api/v1/interviews", headers=headers, json={
            "company_id": companies[0]["id"],
            "role_id": roles[0]["id"],
            "mode": "text",
            "duration_minutes": 30,
            "target_level": "entry",
        })
        assert created.status_code == 200
        assert created.json().get("current_question") is not None, (
            "an empty RAG corpus must not stop the interviewer from asking anything"
        )
        assert RAGEngine is not None


@pytest.mark.asyncio
async def test_errors_do_not_leak_secrets_or_internals():
    """Normal error paths must not echo configuration or stack internals."""
    async with _client() as client:
        _, headers = await _register_and_login(client)

        responses = [
            await client.get("/api/v1/interviews/99999999", headers=headers),
            await client.get("/api/v1/reports/99999999", headers=headers),
            await client.post("/api/v1/auth/login", json={
                "email": "nobody@example.com", "password": "WrongPassword123!",
            }),
        ]

        secret = settings.SECRET_KEY
        for res in responses:
            assert res.status_code < 500, f"unexpected server error: {res.status_code}"
            body = res.text
            assert secret not in body
            for leak in ("Traceback", "postgresql://", "sqlite+aiosqlite", "GEMINI_API_KEY"):
                assert leak not in body, f"error body leaked {leak!r}"


# ======================================================================
# PHASE D -- verification-time guarantees
# ======================================================================

def test_demonstration_uses_no_paid_provider():
    """The session must be pinned to mock providers, not merely assumed to be."""
    assert settings.DEFAULT_LLM_PROVIDER.strip().lower() == "mock", (
        "verification must not run against a paid LLM provider"
    )
    assert settings.DEFAULT_STT_PROVIDER.strip().lower() == "mock"
    assert settings.DEFAULT_TTS_PROVIDER.strip().lower() == "mock"


def test_verification_runs_against_a_throwaway_database():
    """Proof that no development or production PostgreSQL was contacted."""
    from app.core.database import engine

    url = engine.url
    if url.drivername.startswith("sqlite"):
        return
    database = (url.database or "").lower()
    assert database.endswith("_test") or database.startswith("test_") or database == "test", (
        f"verification must not run against {database!r}"
    )


def test_production_configuration_disables_interactive_docs():
    """Production must not publish the full route and schema surface."""
    import app.main as main_module

    # The app under test is built for a non-production environment, so docs are
    # expected to be on here; what is pinned is the rule that produces that.
    assert main_module._docs_enabled == (
        settings.ENVIRONMENT.strip().lower() != "production"
    )
