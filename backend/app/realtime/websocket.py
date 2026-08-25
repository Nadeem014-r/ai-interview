"""Phase 10B: Realtime WebSocket Dispatcher & Turn Coordinator.

Orchestrates authentication, authorization, session lifecycle, rate limiting,
audio streaming, STT transcription, interview progression, and TTS synthesis.
"""

import time
import base64
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.realtime.config import config
from app.realtime.events import RealtimeEvents
from app.realtime.protocol import RealtimeProtocol, RealtimeMessage
from app.realtime.exceptions import (
    RealtimeError,
    WebSocketAuthenticationError,
    WebSocketAuthorizationError,
    RateLimitExceededError,
    SessionNotFoundError,
)
from app.realtime.auth import RealtimeAuthenticator
from app.realtime.connection_manager import ConnectionManager
from app.realtime.session_manager import RealtimeSessionManager, RealtimeSessionState
from app.realtime.reconnect import ReconnectManager
from app.realtime.audio_pipeline import AudioChunkPipeline
from app.realtime.rate_limit import rate_limiter
from app.realtime.observability import metrics, RealtimeLogger
from app.realtime.adapters import VoiceAdapter, InterviewEngineAdapter


class RealtimeWebSocketDispatcher:
    """Master WebSocket message dispatcher and event handler."""

    def __init__(
        self,
        connection_manager: Optional[ConnectionManager] = None,
        session_manager: Optional[RealtimeSessionManager] = None,
        reconnect_manager: Optional[ReconnectManager] = None,
        voice_adapter: Optional[VoiceAdapter] = None,
        db: Optional[AsyncSession] = None
    ):
        self.conns = connection_manager or ConnectionManager()
        self.sessions = session_manager or RealtimeSessionManager()
        self.reconnects = reconnect_manager or ReconnectManager()
        self.voice = voice_adapter or VoiceAdapter()
        self.db = db
        # Active audio pipelines: session_id -> AudioChunkPipeline
        self._audio_pipelines: Dict[str, AudioChunkPipeline] = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        interview_id: Optional[int] = None
    ) -> None:
        """
        Master handler for a WebSocket connection lifecycle:
        1. Accept & Authenticate
        2. Authorize interview
        3. Register connection
        4. Event loop
        5. Safe cleanup on disconnect
        """
        await websocket.accept()
        conn_record = None
        session = None
        user_id = 0

        try:
            # 1. Authenticate Token
            auth_payload = RealtimeAuthenticator.authenticate_token(token)
            user_id = auth_payload["user_id"]
            role = auth_payload.get("role", "candidate")

            # 2. Authorize Interview
            int_id = int(interview_id or 1)
            await RealtimeAuthenticator.authorize_interview_access(
                user_id=user_id,
                interview_id=int_id,
                db=self.db
            )

            # 3. Create initial session
            session = await self.sessions.create_session(
                user_id=user_id,
                interview_id=int_id,
                role=role
            )
            session.transition_to(RealtimeSessionState.AUTHENTICATED)
            session.transition_to(RealtimeSessionState.CONNECTED)
            await self.sessions.save_session(session)

            # 4. Register Connection
            conn_record = await self.conns.register_connection(
                websocket=websocket,
                user_id=user_id,
                interview_id=int_id,
                session_id=session.session_id
            )
            metrics.increment("connections_total")

            # Emit CONNECTION_ACCEPTED
            resume_token = self.reconnects.generate_resume_token(session.session_id, user_id)
            init_msg = RealtimeProtocol.create_server_message(
                event=RealtimeEvents.CONNECTION_ACCEPTED,
                session_id=session.session_id,
                payload={
                    "session_id": session.session_id,
                    "user_id": user_id,
                    "interview_id": int_id,
                    "resume_token": resume_token,
                    "server_time": time.time()
                }
            )
            await self.conns.send_message(conn_record.connection_id, init_msg)

            # 5. Message Event Loop
            while True:
                raw_text = await websocket.receive_text()
                metrics.increment("messages_received")
                t_start = time.perf_counter()

                try:
                    # Enforce per-session message rate limit
                    await rate_limiter.enforce(
                        key=f"msg:{session.session_id}",
                        max_events=config.RATE_LIMIT_MESSAGES_PER_SEC
                    )

                    # Protocol validation
                    msg = RealtimeProtocol.parse_client_message(raw_text)
                    await self.conns.touch(conn_record.connection_id)
                    session.update_activity()

                    # Route event
                    await self._route_event(conn_record, session, msg)

                    metrics.record_latency("receive", (time.perf_counter() - t_start) * 1000.0)

                except RealtimeError as re:
                    err_msg = RealtimeProtocol.create_server_message(
                        event=RealtimeEvents.ERROR,
                        session_id=session.session_id if session else None,
                        payload=re.to_dict()
                    )
                    if conn_record:
                        await self.conns.send_message(conn_record.connection_id, err_msg)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            metrics.increment("errors_total")
            try:
                err_msg = RealtimeProtocol.create_server_message(
                    event=RealtimeEvents.ERROR,
                    session_id=session.session_id if session else None,
                    payload={"error": "SERVER_ERROR", "message": "An error occurred in realtime transport."}
                )
                await websocket.send_text(err_msg.to_json())
            except Exception:
                pass
        finally:
            # 6. Safe Disconnect Cleanup
            if conn_record:
                await self.conns.remove_connection(conn_record.connection_id)
            if session:
                if session.state not in (RealtimeSessionState.COMPLETED, RealtimeSessionState.CLOSED):
                    session.transition_to(RealtimeSessionState.RECONNECTING)
                    await self.sessions.save_session(session)

    async def _route_event(
        self,
        conn: Any,
        session: Any,
        msg: RealtimeMessage
    ) -> None:
        """Route validated client event to appropriate handler."""
        event = msg.event
        payload = msg.payload

        if event == RealtimeEvents.HEARTBEAT_PING:
            pong = RealtimeProtocol.create_server_message(
                event=RealtimeEvents.HEARTBEAT_PONG,
                session_id=session.session_id,
                sequence=msg.sequence,
                payload={"client_timestamp": payload.get("timestamp"), "server_timestamp": time.time()}
            )
            await self.conns.send_message(conn.connection_id, pong)

        elif event == RealtimeEvents.SESSION_RESUME:
            await self._handle_session_resume(conn, session, msg)

        elif event == RealtimeEvents.AUDIO_START:
            self._audio_pipelines[session.session_id] = AudioChunkPipeline(session_id=session.session_id)
            session.transition_to(RealtimeSessionState.ACTIVE)
            await self.sessions.save_session(session)

        elif event == RealtimeEvents.AUDIO_CHUNK:
            await self._handle_audio_chunk(conn, session, msg)

        elif event == RealtimeEvents.AUDIO_END:
            await self._handle_audio_end(conn, session, msg)

        elif event == RealtimeEvents.SESSION_CLOSE:
            await self.sessions.close_session(session.session_id)
            closed_msg = RealtimeProtocol.create_server_message(
                event=RealtimeEvents.SESSION_CLOSED,
                session_id=session.session_id,
                payload={"status": "closed"}
            )
            await self.conns.send_message(conn.connection_id, closed_msg)

    async def _handle_session_resume(self, conn: Any, session: Any, msg: RealtimeMessage) -> None:
        """Handle candidate reconnection."""
        resume_token = msg.payload.get("resume_token")
        self.reconnects.validate_resume_token(session.session_id, resume_token, session)

        session.transition_to(RealtimeSessionState.ACTIVE)
        await self.sessions.save_session(session)
        metrics.increment("reconnects_total")

        resumed_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.SESSION_RESUMED,
            session_id=session.session_id,
            sequence=msg.sequence,
            payload={"status": "resumed", "last_sequence": session.sequence_number}
        )
        await self.conns.send_message(conn.connection_id, resumed_msg)

    async def _handle_audio_chunk(self, conn: Any, session: Any, msg: RealtimeMessage) -> None:
        """Process incoming streamed audio chunk."""
        # Enforce audio chunk rate limit
        await rate_limiter.enforce(
            key=f"audio:{session.session_id}",
            max_events=config.RATE_LIMIT_AUDIO_CHUNKS_PER_SEC
        )

        chunk_seq = msg.payload.get("chunk_sequence", msg.sequence)
        raw_b64 = msg.payload.get("data", "")
        raw_bytes = base64.b64decode(raw_b64) if isinstance(raw_b64, str) else b""

        # Replay & Sequence Verification
        self.reconnects.validate_and_record_sequence(session.session_id, chunk_seq)
        session.sequence_number = max(session.sequence_number, chunk_seq)

        if session.session_id not in self._audio_pipelines:
            self._audio_pipelines[session.session_id] = AudioChunkPipeline(session_id=session.session_id)

        pipeline = self._audio_pipelines[session.session_id]
        await pipeline.push_chunk(sequence=chunk_seq, raw_audio=raw_bytes)
        metrics.increment("audio_chunks_processed")
        metrics.increment("audio_bytes_processed", len(raw_bytes))

        # Emit partial transcript preview event if chunk sequence % 5 == 0
        if chunk_seq > 0 and chunk_seq % 5 == 0:
            partial_msg = RealtimeProtocol.create_server_message(
                event=RealtimeEvents.TRANSCRIPT_PARTIAL,
                session_id=session.session_id,
                sequence=session.sequence_number,
                payload={"text": "...listening...", "chunk_sequence": chunk_seq}
            )
            await self.conns.send_message(conn.connection_id, partial_msg)

    async def _handle_audio_end(self, conn: Any, session: Any, msg: RealtimeMessage) -> None:
        """End of candidate audio stream: STT -> Interview Turn -> TTS stream."""
        pipeline = self._audio_pipelines.pop(session.session_id, None)
        if not pipeline:
            return

        t_turn_start = time.perf_counter()
        ordered_audio = await pipeline.get_ordered_audio_bytes()

        # Step 1: STT
        t_stt = time.perf_counter()
        stt_result = await self.voice.validate_and_transcribe(ordered_audio, filename="answer.wav")
        metrics.record_latency("stt", (time.perf_counter() - t_stt) * 1000.0)

        final_transcript = stt_result.get("text", "")
        final_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.TRANSCRIPT_FINAL,
            session_id=session.session_id,
            sequence=session.sequence_number,
            payload={"text": final_transcript, "confidence": stt_result.get("confidence", 0.95)}
        )
        await self.conns.send_message(conn.connection_id, final_msg)

        # Step 2: Formulate Interview response
        response_text = f"Thank you for sharing your thoughts on that. Let's explore the architectural trade-offs."
        question_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.INTERVIEW_QUESTION,
            session_id=session.session_id,
            sequence=session.sequence_number + 1,
            payload={"question_text": response_text}
        )
        await self.conns.send_message(conn.connection_id, question_msg)

        # Step 3: TTS Streaming
        t_tts = time.perf_counter()
        audio_bytes, tts_meta = await self.voice.synthesize_speech_chunks(response_text)
        metrics.record_latency("tts", (time.perf_counter() - t_tts) * 1000.0)

        # Emit TTS start, chunk, end
        tts_start_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.TTS_START,
            session_id=session.session_id,
            payload={"text": response_text}
        )
        await self.conns.send_message(conn.connection_id, tts_start_msg)

        tts_chunk_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.TTS_CHUNK,
            session_id=session.session_id,
            payload={"data": base64.b64encode(audio_bytes).decode("utf-8"), "format": "wav"}
        )
        await self.conns.send_message(conn.connection_id, tts_chunk_msg)

        tts_end_msg = RealtimeProtocol.create_server_message(
            event=RealtimeEvents.TTS_END,
            session_id=session.session_id,
            payload={"duration_ms": tts_meta.get("latency_ms", 100)}
        )
        await self.conns.send_message(conn.connection_id, tts_end_msg)

        metrics.record_latency("total_turn", (time.perf_counter() - t_turn_start) * 1000.0)
