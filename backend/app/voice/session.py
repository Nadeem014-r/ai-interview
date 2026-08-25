"""Phase 10A: Voice Session Lifecycle & Cancellation Manager.

Provides deterministic voice session lifecycle tracking, illegal transition prevention,
cancellation tokens, and cross-session isolation.
"""

import time
import uuid
from enum import Enum
from typing import Dict, Any, Optional

from app.voice.exceptions import VoiceSessionError, VoiceCancelledError


class VoiceSessionState(str, Enum):
    """Permitted lifecycle states for a voice interaction session."""
    CREATED = "created"
    PROCESSING_STT = "processing_stt"
    TRANSCRIBED = "transcribed"
    PROCESSING_TTS = "processing_tts"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Allowed state transition graph
VALID_TRANSITIONS = {
    VoiceSessionState.CREATED: {VoiceSessionState.PROCESSING_STT, VoiceSessionState.PROCESSING_TTS, VoiceSessionState.CANCELLED, VoiceSessionState.FAILED},
    VoiceSessionState.PROCESSING_STT: {VoiceSessionState.TRANSCRIBED, VoiceSessionState.FAILED, VoiceSessionState.CANCELLED},
    VoiceSessionState.TRANSCRIBED: {VoiceSessionState.PROCESSING_TTS, VoiceSessionState.COMPLETED, VoiceSessionState.FAILED, VoiceSessionState.CANCELLED},
    VoiceSessionState.PROCESSING_TTS: {VoiceSessionState.COMPLETED, VoiceSessionState.FAILED, VoiceSessionState.CANCELLED},
    VoiceSessionState.COMPLETED: set(),  # Terminal
    VoiceSessionState.FAILED: set(),     # Terminal
    VoiceSessionState.CANCELLED: set(),  # Terminal
}


class VoiceSession:
    """Represents an isolated voice interaction session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id: str = session_id or uuid.uuid4().hex
        self.created_at: float = time.time()
        self.state: VoiceSessionState = VoiceSessionState.CREATED
        self.metadata: Dict[str, Any] = {}
        self._is_cancelled: bool = False

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled or self.state == VoiceSessionState.CANCELLED

    def check_cancelled(self) -> None:
        """Raise VoiceCancelledError if session has been marked as cancelled."""
        if self.is_cancelled:
            raise VoiceCancelledError(f"Voice session '{self.session_id}' has been cancelled.")

    def transition_to(self, new_state: VoiceSessionState) -> None:
        """
        Safely transition to a new lifecycle state.
        Raises VoiceSessionError if transition is illegal.
        """
        if self.state == new_state:
            return

        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise VoiceSessionError(f"Illegal session state transition from '{self.state.value}' to '{new_state.value}'.")

        self.state = new_state
        if new_state == VoiceSessionState.CANCELLED:
            self._is_cancelled = True

    def cancel(self) -> None:
        """Cancel this voice session."""
        self._is_cancelled = True
        self.state = VoiceSessionState.CANCELLED


class VoiceSessionManager:
    """Manages active voice sessions with cross-session isolation."""

    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}

    def create_session(self, session_id: Optional[str] = None) -> VoiceSession:
        """Create and register a new isolated voice session."""
        session = VoiceSession(session_id=session_id)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Retrieve an active session by ID."""
        return self._sessions.get(session_id)

    def cancel_session(self, session_id: str) -> bool:
        """Cancel an existing session by ID."""
        session = self.get_session(session_id)
        if session:
            session.cancel()
            return True
        return False

    def close_session(self, session_id: str) -> None:
        """Clean up and remove session from manager."""
        self._sessions.pop(session_id, None)
