"""Phase 10E: Audio Playback Lifecycle & Barge-in Interruption Controller.

Coordinates interviewer audio playback states and handles candidate barge-in safely.
"""

import time
from app.voice_experience.models import TurnState, VoiceTurn
from app.voice_experience.turn_manager import VoiceTurnManager
from app.voice_experience.exceptions import PlaybackError, InterruptionError


class PlaybackController:
    """Controls the lifecycle of synthesized interviewer audio playback."""

    @staticmethod
    def start_playback(turn: VoiceTurn) -> None:
        """Begins playback of synthesized interviewer audio."""
        turn.playback_started_at = time.monotonic()
        VoiceTurnManager.transition(turn, TurnState.PLAYING)

    @staticmethod
    def complete_playback(turn: VoiceTurn) -> None:
        """Marks playback as successfully completed by candidate."""
        turn.completed_at = time.monotonic()
        VoiceTurnManager.transition(turn, TurnState.COMPLETED)

    @staticmethod
    def interrupt_playback(turn: VoiceTurn) -> None:
        """
        Handles candidate interruption / barge-in.
        Halts active playback and transitions turn state safely to INTERRUPTED.
        """
        if turn.state != TurnState.PLAYING:
            return  # Only active playback can be interrupted

        turn.is_interrupted = True
        turn.completed_at = time.monotonic()
        VoiceTurnManager.transition(turn, TurnState.INTERRUPTED)
