"""Phase 10G: Realtime Transport Hardening & Reconnect Storm Defense.

Protects WebSockets against reconnect storms, duplicate/replayed sequence frames, and connection exhaustion.
"""

import time
import threading
from typing import Dict, Set, Tuple, Optional
from app.hardening.exceptions import RateLimitError, ValidationError, ResourceLimitError
from app.hardening.security_policy import SecurityPolicy, default_security_policy


class RealtimeTransportHardening:
    """Manages connection counts, sequence integrity, and replay defense for WebSockets."""

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or default_security_policy
        self._ip_connection_counts: Dict[str, int] = {}
        self._session_sequences: Dict[str, int] = {}       # session_id -> highest_seen_seq
        self._processed_msg_ids: Dict[str, Set[str]] = {}  # session_id -> set of msg_ids
        self._reconnect_timestamps: Dict[str, list] = {}   # client_id -> list of float timestamps
        self._lock = threading.Lock()

    def register_connection(self, client_ip: str) -> None:
        """Enforces IP-based concurrent connection limits."""
        with self._lock:
            current = self._ip_connection_counts.get(client_ip, 0)
            if current >= self.policy.MAX_WS_CONNECTIONS_PER_IP:
                raise ResourceLimitError(f"Connection limit exceeded for IP {client_ip} ({self.policy.MAX_WS_CONNECTIONS_PER_IP} max).")
            self._ip_connection_counts[client_ip] = current + 1

    def release_connection(self, client_ip: str) -> None:
        """Decrements active connection count upon disconnect."""
        with self._lock:
            current = self._ip_connection_counts.get(client_ip, 0)
            if current <= 1:
                self._ip_connection_counts.pop(client_ip, None)
            else:
                self._ip_connection_counts[client_ip] = current - 1

    def check_reconnect_storm(self, client_id: str, window_sec: float = 60.0) -> None:
        """Detects and blocks reconnect storms from runaway clients."""
        with self._lock:
            now = time.monotonic()
            history = self._reconnect_timestamps.get(client_id, [])
            # Evict timestamps older than window
            history = [ts for ts in history if (now - ts) <= window_sec]
            if len(history) >= self.policy.MAX_RECONNECT_ATTEMPTS_PER_MINUTE:
                raise RateLimitError(
                    f"Reconnect storm detected for client '{client_id}'. Throttled.",
                    retry_after_sec=window_sec
                )
            history.append(now)
            self._reconnect_timestamps[client_id] = history

    def validate_message_sequence_and_deduplicate(
        self,
        session_id: str,
        seq: Optional[int],
        msg_id: Optional[str]
    ) -> bool:
        """
        Validates message sequence numbers and prevents duplicate replay execution.
        Returns True if message is new and valid, False if duplicate.
        """
        with self._lock:
            # 1. Message ID Deduplication
            if msg_id:
                seen_ids = self._processed_msg_ids.setdefault(session_id, set())
                if msg_id in seen_ids:
                    return False  # Duplicate message dropped
                seen_ids.add(msg_id)
                if len(seen_ids) > 1000:
                    seen_ids.clear()

            # 2. Sequence ordering
            if seq is not None:
                last_seq = self._session_sequences.get(session_id, -1)
                if seq <= last_seq:
                    return False  # Out of order / duplicate sequence dropped
                self._session_sequences[session_id] = seq

            return True
