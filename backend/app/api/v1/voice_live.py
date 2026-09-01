"""Module 3D: Live Voice WebSocket Router.

Registers two new WebSocket endpoints:
  WS /ws/voice/live/{interview_id}   — Gemini Live API (primary)
  WS /ws/voice/hybrid/{interview_id} — Deepgram+Gemini+ElevenLabs (secondary)

Selection is controlled by the VOICE_PIPELINE_MODE env var:
  "live"   → Gemini Live primary, hybrid fallback
  "hybrid" → Hybrid pipeline directly
  "local"  → Existing WhisperSmallSTTProvider (original pipeline, untouched)

These routes are registered in addition to the existing /ws/voice route.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings

logger = logging.getLogger("ai_interviewer.voice_live")

router = APIRouter(tags=["Real-Time Live Voice"])


@router.websocket("/ws/voice/live/{interview_id}")
async def voice_live_gemini(
    websocket: WebSocket,
    interview_id: int,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Primary WebSocket endpoint using Gemini Live API (full-duplex bidi streaming).

    Supported frontend message types:
      {type: "audio_chunk", data: <base64 PCM 16kHz>, sequence: int}
      {type: "end_of_turn"}
      {type: "ping"}

    Emitted server message types:
      {type: "session_ready"}
      {type: "ai_audio", data: <base64>, mime_type: "audio/pcm;rate=24000"}
      {type: "transcript", role: "user"|"assistant", text: str}
      {type: "ai_turn_complete", latency_ms: int}
      {type: "error", message: str, fallback: bool}
    """
    from app.realtime.gemini_live_dispatcher import GeminiLiveDispatcher

    pipeline_mode = getattr(settings, "VOICE_PIPELINE_MODE", "live").lower()
    logger.info(
        f"Live voice WebSocket: interview={interview_id}, mode={pipeline_mode}"
    )

    await GeminiLiveDispatcher.handle(
        websocket=websocket,
        interview_id=interview_id,
        token=token,
        db=db,
        pipeline_mode=pipeline_mode,
    )


@router.websocket("/ws/voice/hybrid/{interview_id}")
async def voice_hybrid_pipeline(
    websocket: WebSocket,
    interview_id: int,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Fallback WebSocket endpoint using Deepgram Nova-2 STT → Gemini Flash → ElevenLabs TTS.
    Forces hybrid mode regardless of VOICE_PIPELINE_MODE setting.

    Same message protocol as /ws/voice/live/{interview_id}.
    """
    from app.realtime.gemini_live_dispatcher import GeminiLiveDispatcher

    logger.info(f"Hybrid voice WebSocket: interview={interview_id}")

    await GeminiLiveDispatcher.handle(
        websocket=websocket,
        interview_id=interview_id,
        token=token,
        db=db,
        pipeline_mode="hybrid",
    )
