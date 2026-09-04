"""Phase 10E: Voice Experience Models, States & Latency Enums.
"""

import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class TurnState(str, Enum):
    """Lifecycle states of a single conversational voice turn."""
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    GENERATING = "GENERATING"
    SYNTHESIZING = "SYNTHESIZING"
    PLAYING = "PLAYING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


class PermissionState(str, Enum):
    """Client-reported microphone and media permissions."""
    UNKNOWN = "UNKNOWN"
    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


class LatencyClassification(str, Enum):
    """Performance classifications based on response latencies."""
    FAST = "FAST"
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    TIMEOUT = "TIMEOUT"


@dataclass
class VoiceTurn:
    """Represents a discrete candidate-interviewer voice interaction turn."""
    turn_id: str = field(default_factory=lambda: f"turn_{uuid.uuid4().hex[:10]}")
    turn_index: int = 1
    state: TurnState = TurnState.IDLE
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None

    # Timestamps (monotonic)
    stt_started_at: Optional[float] = None
    stt_completed_at: Optional[float] = None
    interview_started_at: Optional[float] = None
    interview_completed_at: Optional[float] = None
    tts_started_at: Optional[float] = None
    tts_completed_at: Optional[float] = None
    playback_started_at: Optional[float] = None

    # Content
    candidate_transcript: Optional[str] = None
    interviewer_response_text: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    audio_format: str = "audio/wav"
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Flags & Diagnostics
    is_interrupted: bool = False
    error: Optional[str] = None

    def get_stt_latency_ms(self) -> float:
        if self.stt_started_at and self.stt_completed_at:
            return round((self.stt_completed_at - self.stt_started_at) * 1000.0, 2)
        return 0.0

    def get_interview_latency_ms(self) -> float:
        if self.interview_started_at and self.interview_completed_at:
            return round((self.interview_completed_at - self.interview_started_at) * 1000.0, 2)
        return 0.0

    def get_tts_latency_ms(self) -> float:
        if self.tts_started_at and self.tts_completed_at:
            return round((self.tts_completed_at - self.tts_started_at) * 1000.0, 2)
        return 0.0

    def get_total_turn_latency_ms(self) -> float:
        end = self.completed_at or time.monotonic()
        return round((end - self.started_at) * 1000.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "turn_index": self.turn_index,
            "state": self.state.value,
            "candidate_transcript": self.candidate_transcript,
            "interviewer_response_text": self.interviewer_response_text,
            "is_interrupted": self.is_interrupted,
            "error": self.error,
            "latencies": {
                "stt_ms": self.get_stt_latency_ms(),
                "interview_ms": self.get_interview_latency_ms(),
                "tts_ms": self.get_tts_latency_ms(),
                "total_ms": self.get_total_turn_latency_ms()
            },
            "metadata": self.metadata
        }
