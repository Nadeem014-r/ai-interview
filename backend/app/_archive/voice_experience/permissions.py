"""Phase 10E: Client Microphone & Media Permission State Handler.

Evaluates client-reported media permissions and provides normalized user messages.
"""

from typing import Tuple
from app._archive.voice_experience.models import PermissionState
from app._archive.voice_experience.exceptions import PermissionDeniedError


class PermissionHandler:
    """Evaluates media permission states without attempting browser bypass."""

    @staticmethod
    def evaluate_permission(state: PermissionState) -> Tuple[bool, str]:
        """
        Validates client media permission.
        Returns (is_allowed, reason_or_instruction).
        """
        if state == PermissionState.GRANTED:
            return True, "Microphone access granted."

        if state == PermissionState.DENIED:
            return False, "Microphone access was denied. Please allow microphone permissions in your browser."

        if state == PermissionState.BLOCKED:
            return False, "Microphone is blocked by system or browser policies."

        if state == PermissionState.UNAVAILABLE:
            return False, "No microphone or audio input device found."

        return False, "Microphone permission has not been requested or granted."

    @classmethod
    def enforce_permission(cls, state: PermissionState) -> None:
        """Raises PermissionDeniedError if microphone access is not granted."""
        allowed, msg = cls.evaluate_permission(state)
        if not allowed:
            raise PermissionDeniedError(msg)
