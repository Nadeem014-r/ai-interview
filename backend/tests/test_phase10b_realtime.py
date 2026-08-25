"""Phase 10B: Comprehensive Realtime Infrastructure Test Suite.

Tests realtime protocol envelopes, WebSocket authentication/authorization,
connection & session lifecycles, reconnect recovery, replay protection,
audio chunk ordering & backpressure, Redis store with in-memory fallback,
rate limiting, background worker, object storage, observability, and Phase 9/10A adapters.
"""

import time
import json
import base64
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import create_access_token
from app.realtime.config import config, RealtimeConfig
from app.realtime.events import RealtimeEvents
from app.realtime.protocol import RealtimeProtocol, RealtimeMessage
from app.realtime.exceptions import (
    RealtimeError,
    WebSocketAuthenticationError,
    WebSocketAuthorizationError,
    InvalidRealtimeMessageError,
    AudioLimitExceededError,
    SessionNotFoundError,
    SessionExpiredError,
    InvalidSessionStateError,
    ReplayDetectedError,
    RateLimitExceededError,
    StorageError,
    BackpressureError,
)
from app.realtime.auth import RealtimeAuthenticator
from app.realtime.connection_manager import ConnectionManager
from app.realtime.session_manager import RealtimeSession, RealtimeSessionState, RealtimeSessionManager
from app.realtime.reconnect import ReconnectManager
from app.realtime.audio_pipeline import AudioChunkPipeline
from app.realtime.redis_store import RedisStore, InMemoryStore
from app.realtime.redis_pubsub import RedisPubSub
from app.realtime.rate_limit import RealtimeRateLimiter
from app.realtime.background import BackgroundJobManager
from app.realtime.storage import LocalStorage
from app.realtime.observability import RealtimeMetrics, RealtimeLogger, RealtimeHealthChecker
from app.realtime.adapters import VoiceAdapter, InterviewEngineAdapter
from app.realtime.websocket import RealtimeWebSocketDispatcher
from app.db.models import Interview, InterviewState


# ==============================================================================
# A & B. Protocol & Event Validation Tests
# ==============================================================================

def test_protocol_valid_client_message():
    """Verify RealtimeProtocol parses valid client message envelope."""
    payload = {"client_timestamp": time.time()}
    raw = json.dumps({
        "version": "1",
        "event": RealtimeEvents.HEARTBEAT_PING,
        "session_id": "sess_test_123",
        "sequence": 1,
        "payload": payload
    })
    msg = RealtimeProtocol.parse_client_message(raw)
    assert msg.event == RealtimeEvents.HEARTBEAT_PING
    assert msg.session_id == "sess_test_123"
    assert msg.sequence == 1
    assert msg.payload == payload


def test_protocol_rejects_unsupported_version_and_unknown_events():
    """Verify RealtimeProtocol rejects invalid protocol versions and unknown client events."""
    # Bad version
    raw_bad_ver = json.dumps({"version": "99", "event": RealtimeEvents.HEARTBEAT_PING, "sequence": 1})
    with pytest.raises(InvalidRealtimeMessageError, match="Unsupported protocol version"):
        RealtimeProtocol.parse_client_message(raw_bad_ver)

    # Unknown event
    raw_bad_event = json.dumps({"version": "1", "event": "arbitrary.unauthorized.event", "sequence": 1})
    with pytest.raises(InvalidRealtimeMessageError, match="Unknown or unauthorized"):
        RealtimeProtocol.parse_client_message(raw_bad_event)


def test_protocol_rejects_malformed_json_and_oversized_payloads():
    """Verify RealtimeProtocol rejects malformed JSON and messages exceeding max size."""
    with pytest.raises(InvalidRealtimeMessageError, match="Malformed JSON"):
        RealtimeProtocol.parse_client_message("NOT_JSON_DATA_STRING")

    huge_payload = {"data": "X" * (config.MAX_MESSAGE_BYTES + 1000)}
    raw_huge = json.dumps({"version": "1", "event": RealtimeEvents.HEARTBEAT_PING, "sequence": 1, "payload": huge_payload})
    with pytest.raises(InvalidRealtimeMessageError, match="exceeds maximum limit"):
        RealtimeProtocol.parse_client_message(raw_huge)


# ==============================================================================
# C & D. Authentication & Authorization Tests
# ==============================================================================

def test_authentication_valid_and_invalid_jwt():
    """Verify RealtimeAuthenticator validates JWT tokens and extracts user ID."""
    token = create_access_token(subject=42, role="candidate")
    claims = RealtimeAuthenticator.authenticate_token(token)
    assert claims["user_id"] == 42
    assert claims["role"] == "candidate"

    # Bearer prefix
    claims_bearer = RealtimeAuthenticator.authenticate_token(f"Bearer {token}")
    assert claims_bearer["user_id"] == 42

    # Invalid token
    with pytest.raises(WebSocketAuthenticationError, match="invalid or expired"):
        RealtimeAuthenticator.authenticate_token("INVALID.JWT.TOKEN")

    # Missing token
    with pytest.raises(WebSocketAuthenticationError, match="Missing authentication token"):
        RealtimeAuthenticator.authenticate_token("")


@pytest.mark.asyncio
async def test_authorization_standalone_and_mismatch():
    """Verify RealtimeAuthenticator validates interview ownership."""
    # Valid candidate ownership
    assert await RealtimeAuthenticator.authorize_interview_access(user_id=10, interview_id=5, candidate_id=10) is True

    # Mismatched candidate ID
    with pytest.raises(WebSocketAuthorizationError, match="mismatch"):
        await RealtimeAuthenticator.authorize_interview_access(user_id=10, interview_id=5, candidate_id=99)


# ==============================================================================
# E, F & G. Connection Manager & Limits Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_connection_manager_lifecycle_and_limits():
    """Verify ConnectionManager registers, tracks, enforces limits, and unregisters connections."""
    mgr = ConnectionManager()
    mock_ws = AsyncMock()

    # Register connection
    conn = await mgr.register_connection(mock_ws, user_id=1, interview_id=100, session_id="s1")
    assert conn.is_active is True
    assert await mgr.active_count() == 1

    # Per-interview limit
    mock_ws2 = AsyncMock()
    mock_ws3 = AsyncMock()
    await mgr.register_connection(mock_ws2, user_id=2, interview_id=100, session_id="s2")

    # 3rd connection for same interview exceeds MAX_CONNECTIONS_PER_INTERVIEW (default 2)
    with pytest.raises(RateLimitExceededError, match="exceeded maximum concurrent connections"):
        await mgr.register_connection(mock_ws3, user_id=3, interview_id=100, session_id="s3")

    # Heartbeat touch
    await mgr.touch(conn.connection_id)

    # Remove connection
    removed = await mgr.remove_connection(conn.connection_id)
    assert removed.connection_id == conn.connection_id
    assert await mgr.active_count() == 1

    # Graceful shutdown
    await mgr.shutdown()
    assert await mgr.active_count() == 0


# ==============================================================================
# H & I. Session Lifecycle & State Machine Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_session_state_machine_and_invalid_transitions():
    """Verify RealtimeSession state machine transitions and invalid transition rejections."""
    session = RealtimeSession(session_id="s_test", user_id=1, interview_id=10)
    assert session.state == RealtimeSessionState.CREATED

    session.transition_to(RealtimeSessionState.AUTHENTICATED)
    session.transition_to(RealtimeSessionState.CONNECTED)
    session.transition_to(RealtimeSessionState.ACTIVE)
    assert session.state == RealtimeSessionState.ACTIVE

    # Illegal: ACTIVE -> CREATED
    with pytest.raises(InvalidSessionStateError, match="Illegal session state transition"):
        session.transition_to(RealtimeSessionState.CREATED)

    session.transition_to(RealtimeSessionState.COMPLETED)
    session.transition_to(RealtimeSessionState.CLOSED)

    # Illegal: CLOSED -> ACTIVE
    with pytest.raises(InvalidSessionStateError, match="Illegal session state transition"):
        session.transition_to(RealtimeSessionState.ACTIVE)


@pytest.mark.asyncio
async def test_session_manager_persistence_and_ttl():
    """Verify RealtimeSessionManager creates, saves, and retrieves sessions with TTL."""
    mgr = RealtimeSessionManager()
    session = await mgr.create_session(user_id=5, interview_id=20, role="candidate")
    assert session.session_id is not None

    loaded = await mgr.get_session(session.session_id)
    assert loaded is not None
    assert loaded.user_id == 5
    assert loaded.interview_id == 20

    await mgr.close_session(session.session_id)
    assert await mgr.get_session(session.session_id) is None


# ==============================================================================
# J, K & L. Reconnection, Replay Protection & Sequence Deduplication Tests
# ==============================================================================

def test_reconnect_manager_tokens_and_replay_protection():
    """Verify ReconnectManager generates tokens, validates grace periods, and prevents replays."""
    reconn = ReconnectManager()
    session = RealtimeSession(session_id="s_rec", user_id=1, interview_id=1)

    # 1. Resume token generation
    token = reconn.generate_resume_token("s_rec", user_id=1)
    assert reconn.validate_resume_token("s_rec", token, session) is True

    # 2. Invalid resume token
    with pytest.raises(WebSocketAuthenticationError, match="Invalid resume token"):
        reconn.validate_resume_token("s_rec", "s_rec.bad_hash_token_string", session)

    # 3. Grace period expiration
    session.last_activity = time.time() - (config.RECONNECT_GRACE_SECONDS + 10)
    with pytest.raises(SessionExpiredError, match="grace period.*expired"):
        reconn.validate_resume_token("s_rec", token, session)

    # 4. Replay / Duplicate sequence detection
    reconn.validate_and_record_sequence("s_rec", sequence=1)
    reconn.validate_and_record_sequence("s_rec", sequence=2)

    with pytest.raises(ReplayDetectedError, match="Duplicate sequence 1"):
        reconn.validate_and_record_sequence("s_rec", sequence=1)


# ==============================================================================
# M, N, O, P & Q. Audio Pipeline, Ordering, Buffer Limits & Backpressure Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_audio_pipeline_ordering_and_deduplication():
    """Verify AudioChunkPipeline buffers out-of-order chunks and releases in sequence."""
    pipeline = AudioChunkPipeline(session_id="s_pipe")

    # Push chunks out of order: Seq 3, Seq 1, Seq 2
    await pipeline.push_chunk(sequence=3, raw_audio=b"Chunk3_")
    await pipeline.push_chunk(sequence=1, raw_audio=b"Chunk1_")
    await pipeline.push_chunk(sequence=2, raw_audio=b"Chunk2_")

    # Push duplicate chunk seq 2 -> should be safely ignored
    await pipeline.push_chunk(sequence=2, raw_audio=b"Chunk2_Duplicate")

    assembled = await pipeline.get_ordered_audio_bytes()
    assert assembled == b"Chunk1_Chunk2_Chunk3_"


@pytest.mark.asyncio
async def test_audio_pipeline_limits_and_backpressure():
    """Verify AudioChunkPipeline enforces chunk size, buffer limits, and queue backpressure."""
    pipeline = AudioChunkPipeline(
        session_id="s_limits",
        max_chunk_bytes=100,
        max_buffer_bytes=250,
        max_queue_size=3
    )

    # 1. Chunk size limit exceeded
    with pytest.raises(AudioLimitExceededError, match="chunk size.*exceeds maximum limit"):
        await pipeline.push_chunk(sequence=1, raw_audio=b"X" * 150)

    # Push valid chunks
    await pipeline.push_chunk(sequence=1, raw_audio=b"A" * 80)
    await pipeline.push_chunk(sequence=2, raw_audio=b"B" * 80)

    # 2. Total buffer limit exceeded (80 + 80 + 100 = 260 > 250)
    with pytest.raises(AudioLimitExceededError, match="Total buffered audio.*exceeds limit"):
        await pipeline.push_chunk(sequence=3, raw_audio=b"C" * 100)

    # 3. Backpressure on queue saturation
    p_queue = AudioChunkPipeline(session_id="s_q", max_chunk_bytes=500, max_buffer_bytes=5000, max_queue_size=2)
    await p_queue.push_chunk(sequence=1, raw_audio=b"1")
    await p_queue.push_chunk(sequence=2, raw_audio=b"2")

    with pytest.raises(BackpressureError, match="backpressure active"):
        await p_queue.push_chunk(sequence=3, raw_audio=b"3")


# ==============================================================================
# R. Sliding-Window Rate Limiting Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_sliding_window_and_enforcement():
    """Verify RealtimeRateLimiter enforces rate limits and returns retry after metadata."""
    limiter = RealtimeRateLimiter()

    # Allowed within limit (2 events per 1s)
    await limiter.enforce(key="user_1", max_events=2, window_seconds=1.0)
    await limiter.enforce(key="user_1", max_events=2, window_seconds=1.0)

    # 3rd event exceeds limit
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.enforce(key="user_1", max_events=2, window_seconds=1.0)

    assert exc_info.value.retry_after_seconds is not None
    assert exc_info.value.retry_after_seconds > 0


# ==============================================================================
# S, T & U. Redis Store, Offline Fallback & Pub/Sub Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_in_memory_and_redis_store_fallback():
    """Verify RedisStore operates with InMemoryStore offline without errors."""
    store = RedisStore(use_redis=False)

    await store.set("key1", "val1", ttl_seconds=10)
    assert await store.get("key1") == "val1"
    assert await store.exists("key1") is True
    assert await store.ttl("key1") > 0

    await store.delete("key1")
    assert await store.get("key1") is None


@pytest.mark.asyncio
async def test_redis_pubsub_local_dispatch():
    """Verify RedisPubSub distributes messages to registered async subscribers."""
    pubsub = RedisPubSub(use_redis=False)
    received = []

    async def on_event(channel: str, message: str):
        received.append((channel, message))

    await pubsub.subscribe("session_events", on_event)
    count = await pubsub.publish("session_events", json.dumps({"action": "start"}))

    assert count == 1
    assert len(received) == 1
    assert received[0][0] == "session_events"
    assert "start" in received[0][1]


# ==============================================================================
# V & W. Background Job Worker & Retries Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_background_job_worker_execution_and_retries():
    """Verify BackgroundJobManager executes tasks with retry on failure and shuts down cleanly."""
    worker = BackgroundJobManager(max_concurrent_jobs=5)
    attempts = 0

    async def flaky_task():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Transient error")
        return "success"

    result = await worker.run_job(flaky_task, max_retries=3, initial_backoff_sec=0.01)
    assert result == "success"
    assert attempts == 2

    # Enqueue non-blocking job
    t = worker.enqueue_job(flaky_task)
    await worker.shutdown(timeout_seconds=1.0)


# ==============================================================================
# X & Y. Object Storage & Path Traversal Sandboxing Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_local_storage_put_get_and_path_traversal_blocking(tmp_path):
    """Verify LocalStorage stores objects and prevents sandbox escaping path traversal."""
    storage = LocalStorage(base_path=str(tmp_path))

    # Valid put and get
    path = await storage.put_object("recordings/rec1.wav", b"AUDIO_BYTES_TEST")
    assert await storage.exists("recordings/rec1.wav") is True
    retrieved = await storage.get_object("recordings/rec1.wav")
    assert retrieved == b"AUDIO_BYTES_TEST"

    # Delete
    assert await storage.delete_object("recordings/rec1.wav") is True
    assert await storage.exists("recordings/rec1.wav") is False

    # Path traversal attack blocked
    with pytest.raises(StorageError, match="Path traversal"):
        await storage.put_object("../../etc/passwd", b"bad_content")


# ==============================================================================
# Z, AA & AB. Observability, Latency Percentiles, Secret Masking & Health Checks
# ==============================================================================

def test_realtime_metrics_percentiles_and_counters():
    """Verify RealtimeMetrics computes accurate P50, P95, P99 monotonic percentiles."""
    m = RealtimeMetrics()
    for val in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
        m.record_latency("total_turn", val)

    p = m.get_percentiles("total_turn")
    assert p["count"] == 10
    assert p["p50"] == 50.0
    assert p["p95"] == 100.0
    assert p["p99"] == 100.0

    m.increment("messages_received", 5)
    assert m.counters["messages_received"] == 5


def test_realtime_logger_masks_sensitive_data():
    """Verify RealtimeLogger masks authorization headers, JWTs, and API keys."""
    raw = "User auth failed for Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.secret and key=AIzaSyTestKey12345"
    masked = RealtimeLogger.mask_sensitive_data(raw)
    assert "eyJhbGci" not in masked
    assert "AIzaSyTestKey12345" not in masked
    assert "[REDACTED_SECRET]" in masked


@pytest.mark.asyncio
async def test_realtime_health_checks():
    """Verify RealtimeHealthChecker reports health status correctly."""
    store = RedisStore(use_redis=False)
    storage = LocalStorage()
    health = await RealtimeHealthChecker.check_health(store, storage)
    assert health["status"] in ("healthy", "degraded")
    assert "websocket_subsystem" in health["components"]


# ==============================================================================
# AC, AD, AE & AF. WebSocket Dispatcher Full Turn Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_websocket_dispatcher_full_turn_integration():
    """Verify complete WebSocket dispatcher turn: Init -> Audio Chunks -> Audio End -> STT -> TTS."""
    dispatcher = RealtimeWebSocketDispatcher()
    mock_ws = AsyncMock()

    sent_messages = []
    async def mock_send_text(text: str):
        sent_messages.append(json.loads(text))

    mock_ws.send_text = mock_send_text

    # Generate test audio
    valid_wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 50
    audio_b64 = base64.b64encode(valid_wav_header).decode("utf-8")

    # Sequence of client messages
    client_events = [
        json.dumps({
            "version": "1",
            "event": RealtimeEvents.HEARTBEAT_PING,
            "sequence": 1,
            "payload": {"timestamp": time.time()}
        }),
        json.dumps({
            "version": "1",
            "event": RealtimeEvents.AUDIO_START,
            "sequence": 2,
            "payload": {}
        }),
        json.dumps({
            "version": "1",
            "event": RealtimeEvents.AUDIO_CHUNK,
            "sequence": 3,
            "payload": {"chunk_sequence": 1, "data": audio_b64}
        }),
        json.dumps({
            "version": "1",
            "event": RealtimeEvents.AUDIO_END,
            "sequence": 4,
            "payload": {}
        }),
        json.dumps({
            "version": "1",
            "event": RealtimeEvents.SESSION_CLOSE,
            "sequence": 5,
            "payload": {}
        })
    ]

    event_index = 0
    async def mock_receive_text():
        nonlocal event_index
        if event_index < len(client_events):
            ev = client_events[event_index]
            event_index += 1
            return ev
        raise asyncio.CancelledError()

    mock_ws.receive_text = mock_receive_text

    # Run dispatcher with test token
    token = create_access_token(subject=1, role="candidate")
    try:
        await dispatcher.handle_connection(mock_ws, token=token, interview_id=1)
    except asyncio.CancelledError:
        pass

    # Verify expected emitted server event types
    emitted_events = [m.get("event") for m in sent_messages]
    assert RealtimeEvents.CONNECTION_ACCEPTED in emitted_events
    assert RealtimeEvents.HEARTBEAT_PONG in emitted_events
    assert RealtimeEvents.TRANSCRIPT_FINAL in emitted_events
    assert RealtimeEvents.INTERVIEW_QUESTION in emitted_events
    assert RealtimeEvents.TTS_START in emitted_events
    assert RealtimeEvents.TTS_CHUNK in emitted_events
    assert RealtimeEvents.TTS_END in emitted_events
    assert RealtimeEvents.SESSION_CLOSED in emitted_events


# ==============================================================================
# AG. Phase 9 and Phase 10A Adapter Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_voice_and_interview_engine_adapters():
    """Verify VoiceAdapter and InterviewEngineAdapter operate without touching Phase 9 or Phase 10A."""
    # VoiceAdapter STT
    valid_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 50
    stt_res = await VoiceAdapter.validate_and_transcribe(valid_wav)
    assert stt_res["success"] is True
    assert len(stt_res["text"]) > 0

    # VoiceAdapter TTS
    audio_bytes, meta = await VoiceAdapter.synthesize_speech_chunks("Hello test prompt")
    assert len(audio_bytes) > 0
    assert meta["success"] is True

    # InterviewEngineAdapter
    mock_interview = Interview(id=1, candidate_id=1, company_id=1, role_id=1, duration_minutes=30, interview_type="technical", target_level="entry")
    mock_state = InterviewState(interview_id=1, current_topic="Python", difficulty="medium", time_remaining_seconds=1800, questions_asked_count=0)
    adapter = InterviewEngineAdapter(db=None)
    state_out, next_q, is_completed = await adapter.advance_interview_turn(mock_interview, mock_state, last_eval_score=8.0, asked_question_ids=[])
    assert state_out.questions_asked_count == 1
    assert is_completed is False


@pytest.mark.asyncio
async def test_concurrent_candidate_isolation():
    """Verify multiple candidates running simultaneous sessions are completely isolated."""
    dispatcher = RealtimeWebSocketDispatcher()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    sent1 = []
    sent2 = []
    ws1.send_text = lambda t: sent1.append(json.loads(t))
    ws2.send_text = lambda t: sent2.append(json.loads(t))

    # Candidate 1 and Candidate 2 tokens
    token1 = create_access_token(subject=101, role="candidate")
    token2 = create_access_token(subject=202, role="candidate")

    # Client messages for Candidate 1
    c1_msg = json.dumps({"version": "1", "event": RealtimeEvents.HEARTBEAT_PING, "sequence": 1})
    c2_msg = json.dumps({"version": "1", "event": RealtimeEvents.HEARTBEAT_PING, "sequence": 1})

    # Step-by-step connection handling
    r1 = await dispatcher.conns.register_connection(ws1, user_id=101, interview_id=1, session_id="s_user1")
    r2 = await dispatcher.conns.register_connection(ws2, user_id=202, interview_id=2, session_id="s_user2")

    assert r1.connection_id != r2.connection_id
    assert r1.session_id != r2.session_id

    # Send targeted message to Candidate 1
    msg1 = RealtimeProtocol.create_server_message(RealtimeEvents.TRANSCRIPT_PARTIAL, session_id="s_user1", payload={"text": "User 1 transcript"})
    await dispatcher.conns.send_message(r1.connection_id, msg1)

    assert len(sent1) == 1
    assert len(sent2) == 0  # Candidate 2 must receive zero messages intended for Candidate 1

    # Cleanup
    await dispatcher.conns.remove_connection(r1.connection_id)
    await dispatcher.conns.remove_connection(r2.connection_id)


@pytest.mark.asyncio
async def test_heartbeat_stale_connection_detection():
    """Verify connection manager detects and purges stale connections exceeding heartbeat timeout."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    conn = await mgr.register_connection(ws, user_id=1, interview_id=1, session_id="s_stale")

    # Manually backdate last_seen
    conn.last_seen = time.time() - 100.0
    stale_list = await mgr.get_stale_connections(timeout_seconds=45.0)

    assert conn.connection_id in stale_list


def test_deployment_configuration_defaults():
    """Verify deployment configuration parameters have valid production defaults."""
    cfg = RealtimeConfig()
    assert cfg.PROTOCOL_VERSION == "1"
    assert cfg.MAX_MESSAGE_BYTES > 0
    assert cfg.MAX_AUDIO_CHUNK_BYTES > 0
    assert cfg.MAX_BUFFER_BYTES > 0
    assert cfg.MAX_GLOBAL_CONNECTIONS > 0
    assert cfg.HEARTBEAT_INTERVAL > 0
    assert cfg.RECONNECT_GRACE_SECONDS >= 30.0

