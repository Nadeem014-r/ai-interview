"""Module 3A: Gemini Live API Full-Duplex Voice Client.

Implements bidirectional WebSocket streaming to the Gemini Live API
(generativelanguage.googleapis.com) for sub-second real-time voice interviews.

Architecture:
  - Input: PCM 16kHz audio chunks (base64) from frontend WebSocket
  - Output: PCM 24kHz audio chunks (base64) back to frontend
  - VAD: Uses Gemini's built-in endOfTurn detection
  - Barge-in: New audio during AI response triggers interruption
  - Fallback: Gracefully degrades to existing RealtimeWebSocketDispatcher

Gemini Live API WebSocket protocol:
  wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta
  .GenerativeService.BidiGenerateContent?key={API_KEY}
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable, Dict, List, Optional, Any

logger = logging.getLogger("ai_interviewer.gemini_live_client")

GEMINI_LIVE_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta"
    ".GenerativeService.BidiGenerateContent"
)

GEMINI_LIVE_MODEL = "models/gemini-2.0-flash-live-001"  # Live API model


class LiveSessionState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    AI_RESPONDING = "ai_responding"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class LiveSessionContext:
    """Carries interview context and persona into the Gemini Live session."""

    interview_id: int
    system_instruction: str
    candidate_name: str = "the candidate"
    role_title: str = "Software Engineer"
    current_topic: str = "General"
    current_depth: int = 1
    session_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_session_config(self, api_key: str) -> Dict[str, Any]:
        return {
            "model": GEMINI_LIVE_MODEL,
            "config": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Aoede"}
                    }
                },
                "systemInstruction": {
                    "parts": [{"text": self.system_instruction}]
                },
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 300,
                }
            }
        }


class GeminiLiveVoiceClient:
    """
    Full-duplex Gemini Live API WebSocket client for real-time voice interviews.

    Usage:
        client = GeminiLiveVoiceClient(api_key, context)
        async for event in client.stream_session(audio_queue, send_to_frontend):
            ...
    """

    def __init__(
        self,
        api_key: str,
        context: LiveSessionContext,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
    ):
        self.api_key = api_key
        self.context = context
        self.on_transcript = on_transcript
        self.on_audio_chunk = on_audio_chunk
        self._state = LiveSessionState.IDLE
        self._ws = None
        self._generation_complete = False
        self._session_start = 0.0

    async def connect_and_stream(
        self,
        audio_input_queue: asyncio.Queue,
        output_queue: asyncio.Queue,
    ) -> None:
        """
        Main entry point. Connects to Gemini Live API and manages bidirectional streaming.

        Args:
            audio_input_queue: asyncio.Queue yielding raw PCM bytes (16kHz)
            output_queue: asyncio.Queue to push outbound messages to frontend
        """
        try:
            import websockets  # type: ignore
        except ImportError:
            logger.error(
                "websockets package not installed. "
                "Run: pip install websockets>=12.0"
            )
            await output_queue.put({
                "type": "error",
                "message": "Gemini Live API client requires websockets package."
            })
            return

        ws_url = f"{GEMINI_LIVE_WS_URL}?key={self.api_key}"
        self._state = LiveSessionState.CONNECTING
        self._session_start = time.monotonic()

        try:
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=10,
                additional_headers={"Content-Type": "application/json"},
            ) as ws:
                self._ws = ws
                self._state = LiveSessionState.CONNECTED
                logger.info(
                    f"GeminiLive connected for interview {self.context.interview_id}"
                )

                # Send session setup
                setup_msg = {
                    "setup": self.context.to_session_config(self.api_key)
                }
                await ws.send(json.dumps(setup_msg))

                # Wait for setup acknowledgement
                setup_ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
                if "setupComplete" not in setup_ack:
                    raise RuntimeError(f"Unexpected setup response: {setup_ack}")

                await output_queue.put({
                    "type": "session_ready",
                    "message": "Gemini Live session established.",
                    "interview_id": self.context.interview_id,
                })

                # Run send and receive loops concurrently
                self._state = LiveSessionState.LISTENING
                await asyncio.gather(
                    self._send_audio_loop(ws, audio_input_queue, output_queue),
                    self._receive_loop(ws, output_queue),
                )

        except asyncio.CancelledError:
            logger.info("GeminiLive session cancelled.")
        except Exception as exc:
            self._state = LiveSessionState.ERROR
            logger.error(f"GeminiLive connection error: {exc}", exc_info=True)
            await output_queue.put({
                "type": "error",
                "message": f"Live voice session error: {str(exc)}",
                "fallback": True,
            })
        finally:
            self._state = LiveSessionState.CLOSED
            self._ws = None

    async def _send_audio_loop(
        self,
        ws: Any,
        audio_input_queue: asyncio.Queue,
        output_queue: asyncio.Queue,
    ) -> None:
        """
        Reads audio chunks from the queue and sends them to Gemini Live.
        Sends endOfTurn signal when the queue signals end of candidate speech.
        """
        while True:
            try:
                item = await asyncio.wait_for(audio_input_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if item is None:  # sentinel: end of stream
                break

            if isinstance(item, dict) and item.get("type") == "end_of_turn":
                # Signal end of candidate speech turn
                turn_end_msg = {
                    "clientContent": {
                        "turns": [],
                        "turnComplete": True
                    }
                }
                await ws.send(json.dumps(turn_end_msg))
                self._state = LiveSessionState.AI_RESPONDING
                self._generation_complete = False
                continue

            # Handle barge-in: if AI is currently responding, send interrupt
            if self._state == LiveSessionState.AI_RESPONDING:
                await self._send_interrupt(ws)
                self._state = LiveSessionState.LISTENING

            # Send PCM audio chunk
            raw_audio: bytes = item if isinstance(item, bytes) else item.get("audio", b"")
            if raw_audio:
                audio_b64 = base64.b64encode(raw_audio).decode("utf-8")
                audio_msg = {
                    "realtimeInput": {
                        "mediaChunks": [
                            {
                                "mimeType": "audio/pcm;rate=16000",
                                "data": audio_b64,
                            }
                        ]
                    }
                }
                await ws.send(json.dumps(audio_msg))

    async def _receive_loop(
        self,
        ws: Any,
        output_queue: asyncio.Queue,
    ) -> None:
        """Receives and dispatches server events from Gemini Live."""
        async for raw_message in ws:
            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            await self._dispatch_server_event(msg, output_queue)

    async def _dispatch_server_event(
        self,
        msg: Dict[str, Any],
        output_queue: asyncio.Queue,
    ) -> None:
        """Route a Gemini Live server message to the appropriate handler."""

        # Audio response chunks
        server_content = msg.get("serverContent")
        if server_content:
            model_turn = server_content.get("modelTurn", {})
            parts = model_turn.get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData", {})
                if inline_data.get("mimeType", "").startswith("audio/"):
                    audio_b64 = inline_data.get("data", "")
                    if audio_b64:
                        await output_queue.put({
                            "type": "ai_audio",
                            "data": audio_b64,
                            "mime_type": inline_data.get("mimeType", "audio/pcm;rate=24000"),
                        })

                # Text transcript
                text = part.get("text", "")
                if text:
                    await output_queue.put({
                        "type": "transcript",
                        "role": "assistant",
                        "text": text,
                    })
                    if self.on_transcript:
                        self.on_transcript(text)

            # Generation complete signal
            if server_content.get("turnComplete"):
                self._generation_complete = True
                self._state = LiveSessionState.LISTENING
                await output_queue.put({"type": "ai_turn_complete"})

            # Interruption acknowledgement
            if server_content.get("interrupted"):
                self._state = LiveSessionState.LISTENING
                await output_queue.put({"type": "ai_interrupted"})

        # Tool call (if configured with function calling)
        tool_call = msg.get("toolCall")
        if tool_call:
            logger.debug(f"GeminiLive tool call received: {tool_call}")

    async def _send_interrupt(self, ws: Any) -> None:
        """Send an interruption signal to stop the current AI response."""
        interrupt_msg = {"clientContent": {"turnComplete": False}}
        try:
            await ws.send(json.dumps(interrupt_msg))
            self._state = LiveSessionState.INTERRUPTED
        except Exception:
            pass

    def get_elapsed_ms(self) -> int:
        return int((time.monotonic() - self._session_start) * 1000)

    @property
    def state(self) -> LiveSessionState:
        return self._state


def build_interview_persona_instruction(
    role_title: str,
    company_name: str,
    candidate_name: str,
    current_topic: str,
    depth: int,
    key_skills: List[str],
) -> str:
    """
    Build the system instruction for the Gemini Live session.
    Produces a concise, terse, professional interviewer persona.
    """
    depth_descriptor = {
        1: "Ask surface-level conceptual questions. Be welcoming and clear.",
        2: "Ask practical implementation questions. Expect code-level reasoning.",
        3: "Ask architectural trade-off questions. Challenge design choices.",
        4: "Ask expert-level scale and failure-mode questions. Be direct, peer-level.",
        5: (
            "Ask advanced research-level questions on cutting-edge topics. "
            "Expect deep system design and optimization expertise."
        ),
    }.get(depth, "Ask contextually appropriate questions.")

    skills_str = ", ".join(key_skills[:6]) if key_skills else role_title

    return f"""You are a senior technical interviewer at {company_name} conducting a real-time voice interview.

PERSONA RULES (follow strictly):
- Be concise: ask ONE clear question per turn, no preamble longer than 1 sentence.
- Do NOT say "Great answer!", "Excellent!", or similar filler affirmations.
- Sound natural and conversational — this is spoken audio.
- You are evaluating {candidate_name} for the {role_title} position.
- Current interview focus: {current_topic}.
- Depth level {depth}/5: {depth_descriptor}
- Core skills to probe: {skills_str}.

FLOW:
- Listen to the candidate's answer.
- If strong (depth {depth} mastered): probe edge cases, trade-offs, or scale.
- If weak (incomplete or incorrect): offer a gentle hint then ask a simpler reformulation.
- Never repeat a question already asked.
- After 2 follow-ups on the same topic, transition to the next competency.

Begin each turn directly with your question. No "Hello" or lengthy introductions mid-session."""
