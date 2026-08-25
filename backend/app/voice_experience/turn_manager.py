"""Phase 10E: Voice Turn State Machine & Transition Validator.

Enforces explicit, valid turn state progression and blocks illegal transitions.
"""

from typing import Set, Dict
from app.voice_experience.models import TurnState, VoiceTurn
from app.voice_experience.exceptions import TurnStateError

VALID_TRANSITIONS: Dict[TurnState, Set[TurnState]] = {
    TurnState.IDLE: {TurnState.LISTENING, TurnState.FAILED},
    TurnState.LISTENING: {TurnState.TRANSCRIBING, TurnState.FAILED},
    TurnState.TRANSCRIBING: {TurnState.THINKING, TurnState.GENERATING, TurnState.FAILED},
    TurnState.THINKING: {TurnState.GENERATING, TurnState.FAILED},
    TurnState.GENERATING: {TurnState.SYNTHESIZING, TurnState.FAILED},
    TurnState.SYNTHESIZING: {TurnState.PLAYING, TurnState.FAILED},
    TurnState.PLAYING: {TurnState.COMPLETED, TurnState.INTERRUPTED, TurnState.FAILED},
    TurnState.INTERRUPTED: {TurnState.LISTENING, TurnState.COMPLETED, TurnState.FAILED},
    TurnState.COMPLETED: set(),  # Terminal state for this turn instance
    TurnState.FAILED: set()      # Terminal state for this turn instance
}


class VoiceTurnManager:
    """Manages state transitions for VoiceTurn instances."""

    @staticmethod
    def transition(turn: VoiceTurn, new_state: TurnState) -> None:
        """
        Transitions turn to new_state.
        Raises TurnStateError if transition is invalid.
        """
        allowed = VALID_TRANSITIONS.get(turn.state, set())
        if new_state not in allowed:
            raise TurnStateError(
                f"Illegal voice turn state transition: '{turn.state.value}' -> '{new_state.value}'."
            )
        turn.state = new_state
