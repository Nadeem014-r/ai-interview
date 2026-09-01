"""Phase 10A: Speech-to-Text Service.

Orchestrates audio validation, timeout enforcement, monotonic latency measurement,
cancellation support, and safe exception normalization for speech transcription.
"""

import asyncio
import re
from typing import Dict, Any, Optional

from app.ai.factory import AIFactory
from app.voice.audio import AudioValidator
from app.voice.latency import LatencyTracker
from app.voice.session import VoiceSession, VoiceSessionState
from app.voice.security import VoiceSecurity
from app.voice.exceptions import (
    STTError,
    STTTimeoutError,
    STTProviderError,
    VoiceCancelledError,
    AudioValidationError,
)


# ---------------------------------------------------------------------------
# Bug Fix 2 – Silence-hallucination post-filter
# Collapses repeated short phrases produced during silence / background noise.
# ---------------------------------------------------------------------------
_HALLUCINATION_REPEAT_RE = re.compile(
    r'(\b[\w\s]{1,15}\b)(?:\s*\1){3,}',
    re.IGNORECASE
)

def deduplicate_hallucination(text: str) -> str:
    """
    Collapse runs of a repeated short phrase (e.g. "Okay. Okay. Okay. Okay.")
    into a single instance.  If the entire transcript degenerates into such
    filler, return an empty string so the caller can discard it as silence.
    """
    if not text:
        return text
    # Replace repeated-phrase run with a single occurrence
    collapsed = _HALLUCINATION_REPEAT_RE.sub(r'\1', text)
    # Secondary pass: remove runs of the same word/punctuation token
    collapsed = re.sub(r'\b(\w+)(?:\s+\1){3,}\b', r'\1', collapsed, flags=re.IGNORECASE)
    collapsed = collapsed.strip()
    # If the result is only 1–2 distinct words after collapsing, treat as filler
    distinct_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', collapsed))
    if len(distinct_words) <= 2 and len(collapsed) < 30:
        # High confidence this was a hallucination loop — discard as silence
        return ""
    return collapsed



class SpeechToTextService:
    """Production STT service with audio validation, timeout, and monotonic latency measurement."""

    @staticmethod
    async def transcribe(
        audio_bytes: bytes,
        filename: str = "recording.wav",
        session: Optional[VoiceSession] = None,
        timeout_seconds: float = 90.0
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes into normalized text.
        1. Checks session cancellation.
        2. Validates audio integrity and headers.
        3. Invokes STT provider with timeout and monotonic latency tracking.
        4. Normalizes and validates transcript.
        """
        tracker = LatencyTracker()

        # 1. Check session cancellation if provided
        if session:
            session.check_cancelled()
            session.transition_to(VoiceSessionState.PROCESSING_STT)

        # 2. Audio Validation Stage
        tracker.start_stage("validation")
        try:
            metadata = AudioValidator.validate_audio(audio_bytes, filename=filename)
        except Exception as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise
        val_latency = tracker.stop_stage("validation")

        # Check cancellation again before calling provider
        if session:
            session.check_cancelled()

        # 3. Provider Invocation Stage with Timeout
        tracker.start_stage("stt")
        stt_provider = AIFactory.get_stt_provider()
        
        try:
            res = await asyncio.wait_for(
                stt_provider.transcribe_audio(audio_bytes, filename=metadata.filename),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise STTTimeoutError(f"STT provider request timed out after {timeout_seconds} seconds.", raw_error=e)
        except VoiceCancelledError:
            if session:
                session.transition_to(VoiceSessionState.CANCELLED)
            raise
        except Exception as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            clean_msg = VoiceSecurity.mask_secrets(str(e))
            raise STTProviderError(f"STT provider failed: {clean_msg}", raw_error=e)

        stt_latency = tracker.stop_stage("stt")

        # 4. Transcript Normalization & Verification
        if not isinstance(res, dict):
            res = {"text": str(res)}

        raw_text = res.get("text") or res.get("transcript") or ""
        # Bug Fix 2: collapse silence-hallucination loops before any further checks
        clean_text = deduplicate_hallucination(raw_text.strip())

        if not clean_text:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise STTError("STT provider returned an empty or whitespace transcript.")

        res["text"] = clean_text
        res["transcript"] = clean_text
        res["latency_ms"] = int(tracker.get_total_latency_ms())
        res["validation_latency_ms"] = val_latency
        res["stt_latency_ms"] = stt_latency
        res["success"] = True
        if "language" not in res:
            res["language"] = "en"

        if session:
            session.transition_to(VoiceSessionState.TRANSCRIBED)
            session.metadata["stt_result"] = res

        return res
