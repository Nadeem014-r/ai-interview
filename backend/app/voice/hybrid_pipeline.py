"""Module 3B: Hybrid Streaming Voice Pipeline.

Fallback Tier B: Deepgram Nova-2 STT → Gemini Flash (streaming) → ElevenLabs Turbo TTS.
Runs as concurrent asyncio pipeline for < 800ms end-to-end latency.

Architecture:
  audio_bytes → DeepgramStreamingSTT → transcript_queue
  transcript_queue → GeminiStreamingLLM → llm_token_queue
  llm_token_queue → ElevenLabsStreamingTTS → audio_output_queue

If Deepgram API key is not configured, falls back to existing WhisperSmallSTTProvider.
If ElevenLabs is unavailable, falls back to existing KokoroTTSProvider.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import AsyncGenerator, Callable, Dict, List, Optional, Any

import httpx

logger = logging.getLogger("ai_interviewer.hybrid_pipeline")


# ---------------------------------------------------------------------------
# Deepgram Streaming STT
# ---------------------------------------------------------------------------

class DeepgramStreamingSTT:
    """
    Streaming Speech-to-Text via Deepgram Nova-2 WebSocket API.
    Falls back to synchronous WhisperSmallSTTProvider if unavailable.
    """

    DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe_stream(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
    ) -> str:
        """
        Send audio bytes to Deepgram Nova-2 and get back transcript.
        Uses streaming WebSocket with a final message await pattern.
        Target: ~150ms TTFB for 1–5 second audio clips.
        """
        if not self.api_key:
            return await self._fallback_transcribe(audio_bytes)

        params = (
            f"model=nova-2&language=en-US"
            f"&sample_rate={sample_rate}&channels=1"
            f"&encoding=linear16&punctuate=true&smart_format=true"
        )
        ws_url = f"{self.DEEPGRAM_WS}?{params}"

        try:
            import websockets  # type: ignore
            async with websockets.connect(
                ws_url,
                additional_headers={"Authorization": f"Token {self.api_key}"},
                ping_interval=None,
            ) as ws:
                # Send audio as a single binary frame
                await ws.send(audio_bytes)
                # Signal end of stream
                await ws.send(json.dumps({"type": "CloseStream"}))

                transcript_parts: List[str] = []
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    channel = msg.get("channel", {})
                    alts = channel.get("alternatives", [])
                    if alts:
                        text = alts[0].get("transcript", "")
                        if text and msg.get("is_final"):
                            transcript_parts.append(text)
                    if msg.get("type") == "Results" and msg.get("speech_final"):
                        break

                return " ".join(transcript_parts).strip()

        except Exception as exc:
            logger.warning(f"Deepgram STT failed: {exc}. Falling back to Whisper.")
            return await self._fallback_transcribe(audio_bytes)

    @staticmethod
    async def _fallback_transcribe(audio_bytes: bytes) -> str:
        """Fallback to existing WhisperSmallSTTProvider."""
        try:
            from app.voice.stt import SpeechToTextService
            result = await SpeechToTextService.transcribe(audio_bytes, filename="recording.wav")
            return result.get("text", "")
        except Exception as exc:
            logger.error(f"Whisper fallback also failed: {exc}")
            return ""


# ---------------------------------------------------------------------------
# Gemini Streaming LLM
# ---------------------------------------------------------------------------

class GeminiStreamingLLM:
    """
    Streams token-by-token responses from Gemini Flash using streaming generateContent.
    Temperature 0.3 for consistent, focused interview responses.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def stream_response(
        self,
        transcript: str,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        max_tokens: int = 200,
    ) -> AsyncGenerator[str, None]:
        """
        Yield text chunks as they stream from Gemini Flash.
        Uses Server-Sent Events (text/event-stream) from generateContent.
        """
        url = f"{self.base_url}/{self.model}:streamGenerateContent?alt=sse"

        # Build contents from conversation history
        contents = []
        for turn in conversation_history[-6:]:  # last 6 turns for context
            role = "user" if turn.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": turn.get("content", "")}]
            })
        # Add current candidate transcript
        contents.append({
            "role": "user",
            "parts": [{"text": transcript}]
        })

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": max_tokens,
                "candidateCount": 1,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST", url, json=payload,
                    headers={"x-goog-api-key": self.api_key},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                candidates = chunk.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        text = part.get("text", "")
                                        if text:
                                            yield text
                            except (json.JSONDecodeError, KeyError):
                                continue
        except Exception as exc:
            logger.error(f"GeminiStreamingLLM error: {exc}")
            yield "Could you please repeat that? I didn't catch your response."


# ---------------------------------------------------------------------------
# ElevenLabs Streaming TTS
# ---------------------------------------------------------------------------

class ElevenLabsStreamingTTS:
    """
    Streams audio from ElevenLabs Turbo v2.5 using their streaming endpoint.
    Yields audio bytes as they arrive (chunk-by-chunk).
    Falls back to KokoroTTSProvider for full synthesis if streaming fails.
    """

    ELEVEN_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    DEFAULT_VOICE_ID = "hqBknhU0QebV576rq8S9"  # from existing .env

    def __init__(self, api_key: str, voice_id: Optional[str] = None):
        self.api_key = api_key
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID

    async def stream_audio(
        self,
        text: str,
    ) -> AsyncGenerator[bytes, None]:
        """
        Yield PCM/MP3 audio bytes as they stream from ElevenLabs.
        Model: eleven_turbo_v2_5 for ultra-low latency (~180ms TTFB).
        """
        if not self.api_key or not text.strip():
            async for chunk in self._fallback_tts(text):
                yield chunk
            return

        url = self.ELEVEN_STREAM_URL.format(voice_id=self.voice_id)
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
            "output_format": "mp3_44100_128",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
        except Exception as exc:
            logger.warning(f"ElevenLabs streaming TTS failed: {exc}. Falling back to Kokoro.")
            async for chunk in self._fallback_tts(text):
                yield chunk

    @staticmethod
    async def _fallback_tts(text: str) -> AsyncGenerator[bytes, None]:
        """Fallback to full synthesis via KokoroTTSProvider."""
        try:
            from app.ai.factory import AIFactory
            tts = AIFactory.get_tts_provider()
            audio_bytes = await tts.synthesize_speech(text, voice_id="default")
            yield audio_bytes
        except Exception as exc:
            logger.error(f"Kokoro TTS fallback also failed: {exc}")
            yield b""


# ---------------------------------------------------------------------------
# Hybrid Pipeline Orchestrator
# ---------------------------------------------------------------------------

class HybridVoicePipeline:
    """
    Concurrent STT → LLM → TTS pipeline targeting < 800ms end-to-end latency.

    Flow:
      1. audio_bytes → DeepgramStreamingSTT → transcript (~150ms)
      2. transcript → GeminiStreamingLLM (streaming) → LLM tokens (~300ms TTFB)
      3. LLM tokens (sentence-boundary batched) → ElevenLabsStreamingTTS (~200ms)
      4. Audio chunks → output_queue → frontend WebSocket
    """

    def __init__(
        self,
        deepgram_api_key: str = "",
        gemini_api_key: str = "",
        elevenlabs_api_key: str = "",
        elevenlabs_voice_id: str = "",
        gemini_model: str = "gemini-2.0-flash-lite",
    ):
        self.stt = DeepgramStreamingSTT(api_key=deepgram_api_key)
        self.llm = GeminiStreamingLLM(api_key=gemini_api_key, model=gemini_model)
        self.tts = ElevenLabsStreamingTTS(
            api_key=elevenlabs_api_key,
            voice_id=elevenlabs_voice_id or None,
        )

    async def process_turn(
        self,
        audio_bytes: bytes,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        output_queue: asyncio.Queue,
    ) -> str:
        """
        Process a complete candidate voice turn:
        1. STT → transcript
        2. Stream LLM → collect tokens with sentence-boundary batching
        3. TTS each sentence → push audio chunks to output_queue

        Returns the full AI response text for session history.
        """
        t0 = time.monotonic()

        # ── Step 1: STT ──────────────────────────────────────────────────────
        transcript = await self.stt.transcribe_stream(audio_bytes)
        if not transcript.strip():
            await output_queue.put({
                "type": "error",
                "message": "Could not transcribe audio — please speak clearly and try again.",
            })
            return ""

        await output_queue.put({
            "type": "transcript",
            "role": "user",
            "text": transcript,
        })

        stt_ms = int((time.monotonic() - t0) * 1000)
        logger.debug(f"HybridPipeline: STT completed in {stt_ms}ms. Transcript: {transcript[:80]}")

        # ── Step 2 + 3: Concurrent LLM streaming + sentence-level TTS ────────
        full_response_parts: List[str] = []
        sentence_buffer = ""

        async for token in self.llm.stream_response(
            transcript=transcript,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        ):
            sentence_buffer += token
            full_response_parts.append(token)

            # Forward text token to frontend
            await output_queue.put({
                "type": "ai_text_chunk",
                "text": token,
            })

            # TTS on sentence boundaries for low latency
            if any(sentence_buffer.rstrip().endswith(p) for p in (".", "!", "?", "...", ":\n")):
                sentence = sentence_buffer.strip()
                sentence_buffer = ""
                if sentence:
                    await self._tts_sentence_to_queue(sentence, output_queue)

        # Handle remaining buffer
        if sentence_buffer.strip():
            await self._tts_sentence_to_queue(sentence_buffer.strip(), output_queue)

        full_response = "".join(full_response_parts).strip()
        total_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"HybridPipeline: full turn completed in {total_ms}ms.")

        await output_queue.put({
            "type": "ai_turn_complete",
            "latency_ms": total_ms,
        })

        return full_response

    async def _tts_sentence_to_queue(
        self,
        sentence: str,
        output_queue: asyncio.Queue,
    ) -> None:
        """TTS a sentence and push audio chunks to the output queue."""
        try:
            async for audio_chunk in self.tts.stream_audio(sentence):
                if audio_chunk:
                    audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                    await output_queue.put({
                        "type": "ai_audio",
                        "data": audio_b64,
                        "mime_type": "audio/mpeg",
                    })
        except Exception as exc:
            logger.warning(f"HybridPipeline: TTS sentence failed: {exc}")


def build_hybrid_pipeline_from_settings() -> HybridVoicePipeline:
    """Factory: construct HybridVoicePipeline from app settings."""
    try:
        from app.core.config import settings
        deepgram_key = getattr(settings, "DEEPGRAM_API_KEY", "") or ""
        gemini_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        elevenlabs_key = getattr(settings, "ELEVENLABS_API_KEY", "") or ""
        elevenlabs_voice = getattr(settings, "ELEVENLABS_VOICE_ID", "") or ""
        model = getattr(settings, "GEMINI_DEFAULT_MODEL", "gemini-2.0-flash-lite")
    except Exception:
        deepgram_key = gemini_key = elevenlabs_key = elevenlabs_voice = ""
        model = "gemini-2.0-flash-lite"

    return HybridVoicePipeline(
        deepgram_api_key=deepgram_key,
        gemini_api_key=gemini_key,
        elevenlabs_api_key=elevenlabs_key,
        elevenlabs_voice_id=elevenlabs_voice,
        gemini_model=model,
    )
