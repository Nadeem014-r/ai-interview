"""Module 3C: Gemini Live WebSocket Dispatcher.

Bridges the frontend WebSocket connection ↔ Gemini Live API WebSocket.
Handles authentication, interview context loading, pipeline selection,
and bidirectional message forwarding.

Message protocol (compatible with existing VoiceInterviewRoom.tsx):
  Frontend → Server:
    {type: "audio_chunk", data: <base64>, sequence: int}
    {type: "end_of_turn"}
    {type: "ping"}

  Server → Frontend:
    {type: "session_ready", message: str}
    {type: "ai_audio", data: <base64>, mime_type: str}
    {type: "ai_text_chunk", text: str}
    {type: "transcript", role: str, text: str}
    {type: "ai_turn_complete", latency_ms: int}
    {type: "ai_interrupted"}
    {type: "error", message: str, fallback: bool}
    {type: "pong"}
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Dict, Any, Optional, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("ai_interviewer.gemini_live_dispatcher")


class GeminiLiveDispatcher:
    """
    Master dispatcher for the Gemini Live API real-time voice WebSocket.

    Handles:
    - JWT authentication via query param token
    - Interview context loading from DB
    - Pipeline selection: Gemini Live (primary) or Hybrid (fallback)
    - Bidirectional audio/message forwarding
    - Graceful error handling and fallback signalling
    """

    @staticmethod
    async def handle(
        websocket: WebSocket,
        interview_id: int,
        token: Optional[str],
        db: Any,
        pipeline_mode: str = "live",
    ) -> None:
        """
        Main WebSocket handler. Called from the voice_live router.

        Args:
            websocket: FastAPI WebSocket connection
            interview_id: Interview DB ID
            token: JWT token from query param
            db: AsyncSession (injected)
            pipeline_mode: "live" | "hybrid" | "local"
        """
        await websocket.accept()

        # ── 1. Authenticate ───────────────────────────────────────────────────
        try:
            from app.realtime.auth import RealtimeAuthenticator
            auth_payload = RealtimeAuthenticator.authenticate_token(token)
            user_id = auth_payload["user_id"]
        except Exception as exc:
            await websocket.send_json({"type": "error", "message": f"Authentication failed: {exc}"})
            await websocket.close(code=4001)
            return

        # ── 2. Load interview context ─────────────────────────────────────────
        context = await GeminiLiveDispatcher._load_context(
            interview_id=interview_id,
            user_id=user_id,
            db=db,
        )
        if context is None:
            await websocket.send_json({
                "type": "error",
                "message": f"Interview {interview_id} not found or not authorized.",
            })
            await websocket.close(code=4004)
            return

        logger.info(
            f"GeminiLiveDispatcher: user={user_id}, interview={interview_id}, "
            f"mode={pipeline_mode}"
        )

        # ── 3. Route to appropriate pipeline ─────────────────────────────────
        try:
            if pipeline_mode == "live":
                await GeminiLiveDispatcher._run_gemini_live(websocket, context)
            else:
                # hybrid or local — use HybridVoicePipeline
                await GeminiLiveDispatcher._run_hybrid_pipeline(websocket, context)
        except WebSocketDisconnect:
            logger.info(f"GeminiLiveDispatcher: client disconnected (interview={interview_id})")
        except Exception as exc:
            logger.error(f"GeminiLiveDispatcher: unhandled error: {exc}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal voice session error.",
                    "fallback": True,
                })
            except Exception:
                pass

    @staticmethod
    async def _load_context(
        interview_id: int,
        user_id: int,
        db: Any,
    ) -> Optional[Dict[str, Any]]:
        """Load interview context from DB and build LiveSessionContext."""
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.db.models import Interview, Resume, Role, Company
            from app.interview.persona_controller import InterviewerPersonaController
            from app.voice.gemini_live_client import LiveSessionContext, build_interview_persona_instruction

            stmt = (
                select(Interview)
                .options(
                    selectinload(Interview.role),
                    selectinload(Interview.company),
                )
                .where(
                    Interview.id == interview_id,
                    Interview.candidate_id == user_id,
                )
            )
            res = await db.execute(stmt)
            interview = res.scalars().first()
            if not interview:
                return None

            role_title = interview.role.title if interview.role else "Software Engineer"
            company_name = interview.company.name if interview.company else "the company"

            # Load candidate name
            from app.db.models import CandidateProfile
            stmt_prof = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
            res_prof = await db.execute(stmt_prof)
            prof = res_prof.scalars().first()
            candidate_name = getattr(prof, "full_name", None) or "the candidate"

            # Load interview state for topic + depth
            from app.db.models import InterviewState
            stmt_state = select(InterviewState).where(InterviewState.interview_id == interview_id)
            res_state = await db.execute(stmt_state)
            istate = res_state.scalars().first()

            current_topic = "Technical Fundamentals"
            current_depth = 1
            key_skills: List[str] = []

            if istate:
                current_topic = istate.current_topic or current_topic
                skill_scores = istate.skill_scores or {}
                key_skills = list(skill_scores.keys())[:6]

            # Build system instruction
            system_instruction = build_interview_persona_instruction(
                role_title=role_title,
                company_name=company_name,
                candidate_name=candidate_name,
                current_topic=current_topic,
                depth=current_depth,
                key_skills=key_skills,
            )

            from app.voice.gemini_live_client import LiveSessionContext
            live_ctx = LiveSessionContext(
                interview_id=interview_id,
                system_instruction=system_instruction,
                candidate_name=candidate_name,
                role_title=role_title,
                current_topic=current_topic,
                current_depth=current_depth,
            )
            return {
                "live_context": live_ctx,
                "system_instruction": system_instruction,
                "interview": interview,
            }
        except Exception as exc:
            logger.error(f"Failed to load interview context: {exc}", exc_info=True)
            return None

    @staticmethod
    async def _run_gemini_live(
        websocket: WebSocket,
        context: Dict[str, Any],
    ) -> None:
        """Run the primary Gemini Live API pipeline."""
        from app.core.config import settings
        from app.voice.gemini_live_client import GeminiLiveVoiceClient

        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            # Fallback to hybrid if no key
            logger.warning("GeminiLiveDispatcher: GEMINI_API_KEY not set, falling back to hybrid.")
            await GeminiLiveDispatcher._run_hybrid_pipeline(websocket, context)
            return

        live_ctx = context["live_context"]
        audio_input_q: asyncio.Queue = asyncio.Queue(maxsize=100)
        output_q: asyncio.Queue = asyncio.Queue(maxsize=200)

        client = GeminiLiveVoiceClient(api_key=api_key, context=live_ctx)

        # Run Gemini Live and frontend I/O concurrently
        async def send_loop():
            """Drain output_q and forward to frontend."""
            while True:
                try:
                    msg = await asyncio.wait_for(output_q.get(), timeout=1.0)
                    await websocket.send_json(msg)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

        async def recv_loop():
            """Receive frontend messages and push to audio_input_q."""
            while True:
                try:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                except (WebSocketDisconnect, Exception):
                    await audio_input_q.put(None)  # signal shutdown
                    break

                mtype = msg.get("type")
                if mtype == "audio_chunk":
                    data_b64 = msg.get("data", "")
                    if data_b64:
                        raw_audio = base64.b64decode(data_b64)
                        await audio_input_q.put(raw_audio)
                elif mtype == "end_of_turn":
                    await audio_input_q.put({"type": "end_of_turn"})
                elif mtype == "ping":
                    await output_q.put({"type": "pong"})

        await asyncio.gather(
            client.connect_and_stream(audio_input_q, output_q),
            send_loop(),
            recv_loop(),
            return_exceptions=True,
        )

    @staticmethod
    async def _run_hybrid_pipeline(
        websocket: WebSocket,
        context: Dict[str, Any],
    ) -> None:
        """Run the fallback Hybrid STT → Gemini Flash → ElevenLabs TTS pipeline."""
        from app.voice.hybrid_pipeline import build_hybrid_pipeline_from_settings

        pipeline = build_hybrid_pipeline_from_settings()
        system_prompt = context.get("system_instruction", "You are a professional technical interviewer.")
        conversation_history: List[Dict[str, str]] = []
        output_q: asyncio.Queue = asyncio.Queue(maxsize=200)

        await websocket.send_json({
            "type": "session_ready",
            "message": "Hybrid voice pipeline ready (STT → LLM → TTS).",
        })

        async def send_loop():
            while True:
                try:
                    msg = await asyncio.wait_for(output_q.get(), timeout=1.0)
                    await websocket.send_json(msg)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

        # Start sender in background
        send_task = asyncio.create_task(send_loop())

        try:
            audio_buffer = bytearray()
            while True:
                try:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                except (WebSocketDisconnect, Exception):
                    break

                mtype = msg.get("type")
                if mtype == "audio_chunk":
                    data_b64 = msg.get("data", "")
                    if data_b64:
                        audio_buffer.extend(base64.b64decode(data_b64))

                elif mtype == "end_of_turn":
                    if audio_buffer:
                        ai_text = await pipeline.process_turn(
                            audio_bytes=bytes(audio_buffer),
                            system_prompt=system_prompt,
                            conversation_history=conversation_history,
                            output_queue=output_q,
                        )
                        if ai_text:
                            conversation_history.append({"role": "assistant", "content": ai_text})
                        audio_buffer.clear()

                elif mtype == "ping":
                    await output_q.put({"type": "pong"})

        finally:
            send_task.cancel()
