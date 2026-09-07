"""Batch 6: end-to-end verification of the real voice interview pipeline.

Every existing "voice" test either exercises the STT/TTS services in isolation or
runs multi-turn interviews with a hardcoded ``answer_text``. Nothing carried a
transcript produced by ``POST /voice/stt`` into ``POST /interviews/{id}/answer``,
so the seam the live demonstration depends on -- audio bytes becoming an
evaluated interview turn -- was never covered.

These tests drive the production route chain the browser actually uses:

    POST /api/v1/voice/stt        (multipart audio, content-derived filename)
      -> SpeechToTextService -> AudioValidator -> STT provider
    POST /api/v1/interviews/{id}/answer   (the transcript, verbatim)
      -> Answer persist -> Evaluation persist -> memory -> adaptive engine
    POST /api/v1/voice/tts        (the next question's text)

Only the external provider boundary is stubbed: the STT provider's
``transcribe_audio``, and the LLM/TTS mock providers the suite already selects
explicitly via tests/conftest.py. Audio validation, magic-byte detection, the
HTTP routes, evaluation, persistence, memory reconstruction, the adaptive engine
and question generation all run for real.

Database safety: the guarded throwaway SQLite database from backend/conftest.py,
with foreign-key enforcement on.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.ai.factory import AIFactory
from app.core.database import AsyncSessionLocal
from app.db.models import Answer, Company, Evaluation, Interview, InterviewState, Role
from app.main import app

# Byte prefixes the real browser produces. MediaRecorder emits WebM/Opus by
# default (VoiceInterviewRoom.tsx); the PCM path encodes a RIFF/WAVE blob.
WEBM_AUDIO = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01" + b"\x00" * 400
WAV_AUDIO = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
) + b"\x00" * 400

STRONG_ANSWER = (
    "Database indexes usually use B+ trees because every leaf sits at the same "
    "depth and the leaves are linked, so range scans stay sequential. That turns "
    "a full scan into a logarithmic descent and cuts disk I/O from O(N) to "
    "O(log N), at the cost of extra writes when the index is maintained."
)
POOR_ANSWER = "no"


class _StubSTTProvider:
    """Stands in for the external STT engine -- the only mocked boundary."""

    def __init__(self):
        self.transcript = STRONG_ANSWER
        self.error = None
        self.calls = 0

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav"):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"transcript": self.transcript, "confidence": 0.94, "duration_sec": 6.0}


@pytest.fixture
def stt(monkeypatch):
    """Replace only the external STT engine; SpeechToTextService stays real."""
    provider = _StubSTTProvider()
    monkeypatch.setattr(
        AIFactory, "get_stt_provider", staticmethod(lambda *a, **k: provider)
    )
    return provider


async def _candidate(client):
    tag = uuid.uuid4().hex[:8]
    email = f"voice_e2e_{tag}@example.com"
    password = "SecurePassword123!"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
        "full_name": f"Voice Candidate {tag}", "role": "candidate",
    })
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _company_and_role():
    async with AsyncSessionLocal() as session:
        company = (await session.execute(
            select(Company).options(selectinload(Company.roles)).order_by(Company.id)
        )).scalars().first()
        assert company is not None and company.roles
        return company.id, company.roles[0].id


async def _start_voice_interview(client, headers):
    company_id, role_id = await _company_and_role()
    res = await client.post("/api/v1/interviews", headers=headers, json={
        "company_id": company_id, "role_id": role_id,
        "mode": "audio", "interview_type": "technical",
        "duration_minutes": 30, "target_level": "entry",
    })
    assert res.status_code == 200, res.text
    return res.json()["id"]


async def _transcribe(client, headers, audio=WEBM_AUDIO, filename="answer_turn.webm"):
    """The exact upload the frontend performs."""
    return await client.post(
        "/api/v1/voice/stt",
        headers=headers,
        files={"file": (filename, audio, "application/octet-stream")},
    )


async def _voice_turn(client, headers, interview_id, stt, transcript,
                      audio=WEBM_AUDIO, filename="answer_turn.webm"):
    """One full spoken turn: audio -> transcript -> evaluated interview turn."""
    stt.transcript = transcript
    stt_res = await _transcribe(client, headers, audio, filename)
    assert stt_res.status_code == 200, stt_res.text
    spoken = stt_res.json()["transcript"]

    ans_res = await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        headers=headers,
        json={"answer_text": spoken, "audio_url": "blob:local/turn", "stt_latency_ms": 0},
    )
    return stt_res, ans_res


async def _db_counts(interview_id):
    async with AsyncSessionLocal() as session:
        answers = (await session.execute(
            select(Answer).where(Answer.interview_id == interview_id).order_by(Answer.id)
        )).scalars().all()
        evaluations = (await session.execute(
            select(func.count()).select_from(Evaluation).where(
                Evaluation.answer_id.in_([a.id for a in answers]) if answers else False
            )
        )).scalar() or 0
        state = (await session.execute(
            select(InterviewState).where(InterviewState.interview_id == interview_id)
        )).scalars().first()
        return answers, evaluations, state


# ======================================================================
# Scenario A -- one successful spoken turn, end to end
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_a_successful_voice_turn(stt):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        stt_res, ans_res = await _voice_turn(client, headers, interview_id, stt, STRONG_ANSWER)

        # STT contract the frontend reads: sttData.transcript || sttData.text
        body = stt_res.json()
        assert body["transcript"] == STRONG_ANSWER
        assert body["text"] == STRONG_ANSWER
        assert body["success"] is True
        assert "latency_ms" in body
        assert stt.calls == 1

        # The interview turn really happened
        assert ans_res.status_code == 200, ans_res.text
        turn = ans_res.json()
        assert turn["evaluation"]["overall_question_score"] > 0
        assert turn["interview_state"]["questions_asked_count"] == 1
        if not turn["is_completed"]:
            assert turn["next_question"]["question_text"].strip()

            # The next question is spoken back to the candidate
            tts = await client.post("/api/v1/voice/tts", headers=headers,
                                    json={"text": turn["next_question"]["question_text"]})
            assert tts.status_code == 200
            assert len(tts.content) > 0
            assert tts.headers["content-type"].startswith("audio/")

    answers, evaluations, state = await _db_counts(interview_id)
    assert len(answers) == 1
    assert answers[0].candidate_answer_text == STRONG_ANSWER
    assert evaluations == 1
    assert state is not None


# ======================================================================
# Scenario B -- three consecutive spoken turns
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_b_multiple_voice_turns_stay_consistent(stt):
    transcripts = [
        STRONG_ANSWER,
        "I would shard by tenant id and keep a routing table, then use consistent "
        "hashing so rebalancing moves a bounded number of keys.",
        "For concurrency I rely on async I/O with a bounded worker pool, and I "
        "measure tail latency rather than averages before tuning anything.",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        question_ids = []
        for index, transcript in enumerate(transcripts, start=1):
            before = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
            question_ids.append(before["current_question"]["id"])

            _, ans_res = await _voice_turn(client, headers, interview_id, stt, transcript)
            assert ans_res.status_code == 200, ans_res.text
            turn = ans_res.json()
            assert turn["interview_state"]["questions_asked_count"] == index
            if turn["is_completed"]:
                break

    answers, evaluations, state = await _db_counts(interview_id)
    # Every spoken turn produced exactly one answer and one evaluation
    assert len(answers) == len(transcripts)
    assert evaluations == len(answers)
    # Turn ordering preserved, and each answer is the transcript that was spoken
    assert [a.candidate_answer_text for a in answers] == transcripts
    # No duplicate processing: each answer belongs to a distinct question
    assert len({a.question_id for a in answers}) == len(answers)
    # All answers belong to this interview only
    assert {a.interview_id for a in answers} == {interview_id}
    assert len(set(question_ids)) == len(question_ids), "the same question was re-asked"
    assert stt.calls == len(transcripts)


# ======================================================================
# Scenario C/D/E/F -- adaptive follow-up and recovery reached via voice
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_cd_poor_spoken_answers_reach_recovery(stt):
    """Consecutive poor spoken answers must drive the real adaptive machinery."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        stages, scores = [], []
        for _ in range(3):
            _, ans_res = await _voice_turn(client, headers, interview_id, stt, POOR_ANSWER)
            assert ans_res.status_code == 200, ans_res.text
            turn = ans_res.json()
            stages.append(turn["interview_state"]["interview_stage"])
            scores.append(turn["evaluation"]["overall_question_score"])
            if turn["is_completed"]:
                break

    # Poor spoken answers are scored as poor -- never fabricated upward
    assert all(s <= 3.0 for s in scores), scores
    # The engine reacted: it either offered recovery or concluded early
    assert any(stage in ("recovery", "early_conclusion") for stage in stages), stages

    answers, evaluations, _ = await _db_counts(interview_id)
    assert evaluations == len(answers), "an unevaluated voice answer was left behind"


@pytest.mark.asyncio
async def test_scenario_ef_recovery_outcome_follows_the_evaluation(stt):
    """A fluent but empty recovery answer must not pass; a real one must."""
    async def _run(recovery_transcript):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _candidate(client)
            interview_id = await _start_voice_interview(client, headers)

            stage = None
            for _ in range(3):
                _, ans_res = await _voice_turn(client, headers, interview_id, stt, POOR_ANSWER)
                turn = ans_res.json()
                stage = turn["interview_state"]["interview_stage"]
                if stage == "recovery" or turn["is_completed"]:
                    break

            if stage != "recovery":
                pytest.skip("engine concluded before offering recovery; covered by scenario C/D")

            _, ans_res = await _voice_turn(client, headers, interview_id, stt, recovery_transcript)
            assert ans_res.status_code == 200, ans_res.text
            return ans_res.json()

    # Failed recovery: long, fluent, but explicitly no knowledge.
    fluent_but_empty = (
        "Honestly I have absolutely no idea about this topic and I have never "
        "studied it at all, I really do not know anything about it, sorry, I "
        "cannot answer this question because I do not know the answer."
    )
    failed = await _run(fluent_but_empty)
    assert failed["evaluation"]["overall_question_score"] <= 4.0, (
        "a fluent non-answer must not be scored as a successful recovery"
    )

    # Successful recovery: genuine substance keeps the interview going.
    succeeded = await _run(STRONG_ANSWER)
    assert succeeded["evaluation"]["overall_question_score"] > 4.0
    assert succeeded["interview_state"]["interview_stage"] != "early_conclusion"


# ======================================================================
# Scenario G -- the STT provider fails
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_g_stt_failure_does_not_touch_interview_state(stt):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        before = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()

        stt.error = RuntimeError("stt engine exploded")
        failed = await _transcribe(client, headers)

        assert failed.status_code >= 400, "a failed transcription must not report success"
        assert "transcript" not in failed.json()

        after = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
        assert after["current_question"]["id"] == before["current_question"]["id"]
        assert after["state"]["questions_asked_count"] == before["state"]["questions_asked_count"]

        # Retrying after the failure produces exactly one turn, not two
        stt.error = None
        _, ans_res = await _voice_turn(client, headers, interview_id, stt, STRONG_ANSWER)
        assert ans_res.status_code == 200, ans_res.text

    answers, evaluations, _ = await _db_counts(interview_id)
    assert len(answers) == 1, "the failed attempt persisted an answer"
    assert evaluations == 1


# ======================================================================
# Scenario H -- STT succeeds but returns nothing
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_h_empty_transcript_is_never_an_answer(stt):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        for blank in ("", "   ", "\n\t "):
            stt.transcript = blank
            res = await _transcribe(client, headers)
            assert res.status_code >= 400, f"blank transcript {blank!r} was accepted"
            assert "transcript" not in res.json()

        # The answer endpoint independently refuses a blank answer
        blank_answer = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            headers=headers,
            json={"answer_text": "   ", "audio_url": None, "stt_latency_ms": 0},
        )
        assert blank_answer.status_code == 400

    answers, evaluations, _ = await _db_counts(interview_id)
    assert answers == []
    assert evaluations == 0


# ======================================================================
# Scenario I -- TTS fails after a successful turn
# ======================================================================

@pytest.mark.asyncio
async def test_scenario_i_tts_failure_leaves_the_turn_intact(stt, monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        _, ans_res = await _voice_turn(client, headers, interview_id, stt, STRONG_ANSWER)
        assert ans_res.status_code == 200, ans_res.text
        turn = ans_res.json()
        next_text = (turn.get("next_question") or {}).get("question_text") or "Fallback question."

        from app.voice.tts import TextToSpeechService

        async def _boom(*args, **kwargs):
            raise RuntimeError("tts engine offline")

        monkeypatch.setattr(TextToSpeechService, "synthesize", _boom)

        tts = await client.post("/api/v1/voice/tts", headers=headers, json={"text": next_text})
        # Whatever the configured degradation is, it must not be a crash and the
        # question text is already in the candidate's hands either way.
        assert tts.status_code in (200, 503), tts.text

        # Retrying TTS must never create another interview turn
        await client.post("/api/v1/voice/tts", headers=headers, json={"text": next_text})

        state = (await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)).json()
        assert state["state"]["questions_asked_count"] == 1

    answers, evaluations, _ = await _db_counts(interview_id)
    assert len(answers) == 1, "TTS retry duplicated the interview turn"
    assert evaluations == 1


# ======================================================================
# Scenario J -- real browser audio formats; content decides, not the name
# ======================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("audio,filename,label", [
    (WEBM_AUDIO, "answer_turn.webm", "webm content, webm name (Chrome/Firefox default)"),
    (WAV_AUDIO, "answer_turn.wav", "wav content, wav name (PCM path)"),
    (WEBM_AUDIO, "answer_turn.wav", "webm content, mismatched wav name"),
    # FormData.append("file", blob) with no third argument -- the browser names
    # the part "blob", with no extension at all. An *empty* filename is not
    # reachable from a browser: multipart omits the filename parameter
    # entirely, so the part stops being a file upload and FastAPI rejects it
    # before any voice code runs.
    (WEBM_AUDIO, "blob", "webm content, extensionless browser default name"),
])
async def test_scenario_j_browser_audio_is_classified_by_content(stt, audio, filename, label):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        res = await _transcribe(client, headers, audio=audio, filename=filename)
        assert res.status_code == 200, f"{label} rejected: {res.text}"
        assert res.json()["transcript"] == STRONG_ANSWER


@pytest.mark.asyncio
async def test_scenario_j_unknown_audio_is_rejected_as_client_error(stt):
    """An unrecognised header is a bad upload, not a server fault."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        res = await _transcribe(client, headers, audio=b"\x00\x01\x02\x03" + b"\x00" * 400,
                                filename="answer_turn.webm")
        assert res.status_code == 400, res.text
        assert stt.calls == 0, "an invalid payload reached the STT provider"


# ======================================================================
# Scenario K -- short spoken answers survive the hallucination filter
# ======================================================================

# Whisper emits a looping phrase when it is fed silence or background noise.
# These are the transcripts that genuinely must be discarded.
SILENCE_HALLUCINATIONS = [
    "Okay. Okay. Okay. Okay.",
    "okay okay okay okay",
    "Thank you. Thank you. Thank you. Thank you.",
    "you you you you you",
]

# These are complete spoken answers. Several are *correct*. The silence filter
# used to delete every one of them, because it discarded any transcript with at
# most two distinct words and fewer than 30 characters -- a rule that keys on
# shortness rather than on repetition. A candidate who answered "B-trees"
# received HTTP 500 and lost the turn.
LEGITIMATE_SHORT_ANSWERS = [
    "no",
    "yes",
    "B-trees",
    "Binary search",
    "No idea",
    "I don't know",
    "Hash tables and B-trees",
    "cache miss cache hit",
]


@pytest.mark.parametrize("transcript", LEGITIMATE_SHORT_ANSWERS)
def test_short_real_answers_are_not_discarded_as_silence(transcript):
    from app.voice.stt import deduplicate_hallucination

    assert deduplicate_hallucination(transcript) == transcript


@pytest.mark.parametrize("transcript", SILENCE_HALLUCINATIONS)
def test_silence_loops_are_still_discarded(transcript):
    from app.voice.stt import deduplicate_hallucination

    assert deduplicate_hallucination(transcript) == ""


def test_a_long_answer_that_repeats_words_naturally_is_kept():
    """The repetition rule must not punish ordinary spoken redundancy."""
    from app.voice.stt import deduplicate_hallucination

    spoken = (
        "I think that the answer is that the system uses the cache to store "
        "the data so that the next request can read the data from the cache."
    )
    assert deduplicate_hallucination(spoken) == spoken


@pytest.mark.asyncio
async def test_scenario_k_short_spoken_answer_becomes_a_real_turn(stt):
    """The full route chain, driven by a correct one-word spoken answer."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        stt_res, ans_res = await _voice_turn(client, headers, interview_id, stt, "B-trees")

        assert stt_res.status_code == 200, stt_res.text
        assert stt_res.json()["transcript"] == "B-trees"
        assert ans_res.status_code == 200, ans_res.text
        assert ans_res.json()["interview_state"]["questions_asked_count"] == 1

    answers, evaluations, _ = await _db_counts(interview_id)
    assert [a.candidate_answer_text for a in answers] == ["B-trees"]
    assert evaluations == 1


@pytest.mark.asyncio
async def test_scenario_k_silent_recording_is_a_client_error_not_a_server_fault(stt):
    """Silence must not be reported to the candidate as a server crash."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)

        stt.transcript = "Okay. Okay. Okay. Okay."
        res = await _transcribe(client, headers)

        assert res.status_code == 400, res.text
        assert "transcript" not in res.json()
        assert "no speech" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stt_provider_outage_is_still_a_server_error(stt):
    """A genuine provider failure must stay a 5xx, not be masked as a bad upload."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)

        stt.error = RuntimeError("provider offline")
        res = await _transcribe(client, headers)

        assert res.status_code >= 500, res.text
        assert "transcript" not in res.json()


# ======================================================================
# Scenario L -- a malformed STT response must never become a transcript
# ======================================================================

class _MalformedSTTProvider:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav"):
        self.calls += 1
        return self.value


# The shapes a real SDK returns when it fails without raising. `None` is the
# common one: the service used to coerce it with str(), handing back the literal
# transcript "None", which was then persisted and evaluated as the candidate's
# own spoken answer.
@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", [None, 12345, ["a", "b"], object()])
async def test_malformed_stt_response_is_not_coerced_into_a_transcript(monkeypatch, malformed):
    from app.voice.exceptions import STTProviderError
    from app.voice.stt import SpeechToTextService

    provider = _MalformedSTTProvider(malformed)
    monkeypatch.setattr(
        AIFactory, "get_stt_provider", staticmethod(lambda *a, **k: provider)
    )
    with pytest.raises(STTProviderError):
        await SpeechToTextService.transcribe(WAV_AUDIO)


@pytest.mark.asyncio
@pytest.mark.parametrize("well_formed,expected", [
    ("a bare transcript string", "a bare transcript string"),
    ({"text": "dict with text"}, "dict with text"),
    ({"transcript": "dict with transcript"}, "dict with transcript"),
])
async def test_well_formed_stt_responses_still_work(monkeypatch, well_formed, expected):
    """The strictness must not break providers that answer correctly."""
    from app.voice.stt import SpeechToTextService

    provider = _MalformedSTTProvider(well_formed)
    monkeypatch.setattr(
        AIFactory, "get_stt_provider", staticmethod(lambda *a, **k: provider)
    )
    res = await SpeechToTextService.transcribe(WAV_AUDIO)
    assert res["transcript"] == expected


@pytest.mark.asyncio
async def test_malformed_stt_response_never_reaches_the_interview(monkeypatch):
    """A None from the provider must not be submittable as an answer."""
    provider = _MalformedSTTProvider(None)
    monkeypatch.setattr(
        AIFactory, "get_stt_provider", staticmethod(lambda *a, **k: provider)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _candidate(client)
        interview_id = await _start_voice_interview(client, headers)

        res = await _transcribe(client, headers)
        assert res.status_code >= 400, res.text
        assert "transcript" not in res.json()
        assert "None" not in str(res.json().get("detail", "")).split("type")[0]

    answers, evaluations, _ = await _db_counts(interview_id)
    assert answers == [], "a fabricated transcript was persisted as an answer"
    assert evaluations == 0
