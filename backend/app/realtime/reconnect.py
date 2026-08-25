"""Phase 10B: Reconnect & Session Recovery Manager.

Handles resume token issuance, reconnection grace-period enforcement,
sequence reconciliation, and replay protection.
"""

import time
import hmac
import hashlib
import secrets
from typing import Dict, Optional, Tuple, Set

from app.core.config import settings
from app.realtime.config import config
from app.realtime.session_manager import RealtimeSession, RealtimeSessionState
from app.realtime.exceptions import (
    SessionNotFoundError,
    SessionExpiredError,
    ReplayDetectedError,
    WebSocketAuthenticationError,
)


class ReconnectManager:
    """Manages reconnection tokens, grace periods, and replay deduplication."""

    def __init__(self):
        # session_id -> (resume_token_hash, created_at)
        self._tokens: Dict[str, Tuple[str, float]] = {}
        # session_id -> set of processed sequence numbers for replay protection
        self._processed_sequences: Dict[str, Set[int]] = {}

    def generate_resume_token(self, session_id: str, user_id: int) -> str:
        """Generate a cryptographically secure resume token for a session."""
        raw_secret = secrets.token_urlsafe(32)
        token_data = f"{session_id}:{user_id}:{raw_secret}"
        token_hash = hmac.new(settings.SECRET_KEY.encode(), token_data.encode(), hashlib.sha256).hexdigest()
        self._tokens[session_id] = (token_hash, time.time())
        return f"{session_id}.{token_hash}"

    def validate_resume_token(
        self,
        session_id: str,
        resume_token: Optional[str],
        session: RealtimeSession
    ) -> bool:
        """
        Validates reconnection token within the allowed grace period window.
        Raises appropriate exceptions if token is invalid or grace period expired.
        """
        if not resume_token or not resume_token.strip():
            raise WebSocketAuthenticationError("Missing resume token for reconnection.")

        parts = resume_token.strip().split(".")
        if len(parts) != 2 or parts[0] != session_id:
            raise WebSocketAuthenticationError("Malformed or mismatched resume token.")

        provided_hash = parts[1]
        stored = self._tokens.get(session_id)
        if not stored:
            raise WebSocketAuthenticationError("No active resume token found for this session.")

        stored_hash, token_created_at = stored

        # Grace period check
        time_since_disconnect = time.time() - session.last_activity
        if time_since_disconnect > config.RECONNECT_GRACE_SECONDS:
            raise SessionExpiredError(f"Reconnection grace period ({config.RECONNECT_GRACE_SECONDS}s) expired ({time_since_disconnect:.1f}s elapsed).")

        if not hmac.compare_digest(provided_hash, stored_hash):
            raise WebSocketAuthenticationError("Invalid resume token.")

        return True

    def validate_and_record_sequence(self, session_id: str, sequence: int) -> None:
        """
        Replay & Duplicate Detection:
        Verifies that sequence has not been processed already for this session.
        """
        if session_id not in self._processed_sequences:
            self._processed_sequences[session_id] = set()

        processed = self._processed_sequences[session_id]
        if sequence in processed:
            raise ReplayDetectedError(f"Duplicate sequence {sequence} detected for session {session_id}.")

        processed.add(sequence)
        # Cap set size to avoid unbounded memory growth
        if len(processed) > 5000:
            min_seq = min(processed)
            processed.remove(min_seq)

    def cleanup_session(self, session_id: str) -> None:
        """Clean up resume tokens and sequence sets for a closed session."""
        self._tokens.pop(session_id, None)
        self._processed_sequences.pop(session_id, None)
