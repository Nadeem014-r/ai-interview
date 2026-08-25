"""Phase 10E: Audio Lifecycle & Turn Buffer Cleanup Manager.

Provides idempotent, exception-safe cleanup of transient audio payloads and turn buffers.
"""

from typing import Optional, Dict
from app.voice_experience.models import VoiceTurn


class AudioLifecycleManager:
    """Manages audio retention policies and temporary buffer deletion."""

    @staticmethod
    def cleanup_turn_audio(turn: VoiceTurn, preserve_metadata: bool = True) -> None:
        """
        Clears raw audio bytes from memory after turn processing completes.
        Preserves transcript and timing metadata.
        """
        if turn:
            turn.audio_bytes = None
            if not preserve_metadata:
                turn.metadata.clear()

    @staticmethod
    def release_session_buffers(session_turns: Dict[str, VoiceTurn]) -> int:
        """Clears audio buffers across an entire session."""
        cleaned_count = 0
        for turn in session_turns.values():
            if turn.audio_bytes is not None:
                turn.audio_bytes = None
                cleaned_count += 1
        return cleaned_count
