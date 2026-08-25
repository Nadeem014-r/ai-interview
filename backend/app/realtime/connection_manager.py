"""Phase 10B: Realtime WebSocket Connection Manager.

Manages active WebSocket connections, enforces concurrency limits per user/interview,
tracks heartbeats, and ensures thread/async safety without race conditions.
"""

import time
import uuid
import asyncio
from typing import Dict, Any, Optional, Set, List
from fastapi import WebSocket

from app.realtime.config import config
from app.realtime.protocol import RealtimeMessage
from app.realtime.exceptions import RealtimeError, RateLimitExceededError


class ConnectionRecord:
    """Represents an active WebSocket connection."""

    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        user_id: int,
        interview_id: int,
        session_id: str
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.interview_id = interview_id
        self.session_id = session_id
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.is_active = True

    def touch(self) -> None:
        self.last_seen = time.time()


class ConnectionManager:
    """Async-safe connection registry with per-user, per-interview, and global limits."""

    def __init__(self):
        # connection_id -> ConnectionRecord
        self._connections: Dict[str, ConnectionRecord] = {}
        # user_id -> Set[connection_id]
        self._user_connections: Dict[int, Set[str]] = {}
        # interview_id -> Set[connection_id]
        self._interview_connections: Dict[int, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def register_connection(
        self,
        websocket: WebSocket,
        user_id: int,
        interview_id: int,
        session_id: str
    ) -> ConnectionRecord:
        """
        Registers a new WebSocket connection while enforcing concurrency limits.
        Raises RateLimitExceededError or RealtimeError if limits are breached.
        """
        async with self._lock:
            # 1. Global limit
            if len(self._connections) >= config.MAX_GLOBAL_CONNECTIONS:
                raise RateLimitExceededError("Server is at maximum concurrent connection capacity.")

            # 2. Per-user limit
            user_conns = self._user_connections.get(user_id, set())
            if len(user_conns) >= config.MAX_CONNECTIONS_PER_USER:
                raise RateLimitExceededError(f"User {user_id} exceeded maximum concurrent connections ({config.MAX_CONNECTIONS_PER_USER}).")

            # 3. Per-interview limit
            int_conns = self._interview_connections.get(interview_id, set())
            if len(int_conns) >= config.MAX_CONNECTIONS_PER_INTERVIEW:
                raise RateLimitExceededError(f"Interview {interview_id} exceeded maximum concurrent connections ({config.MAX_CONNECTIONS_PER_INTERVIEW}).")

            cid = f"conn_{uuid.uuid4().hex}"
            record = ConnectionRecord(
                connection_id=cid,
                websocket=websocket,
                user_id=user_id,
                interview_id=interview_id,
                session_id=session_id
            )

            self._connections[cid] = record
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(cid)

            if interview_id not in self._interview_connections:
                self._interview_connections[interview_id] = set()
            self._interview_connections[interview_id].add(cid)

            return record

    async def remove_connection(self, connection_id: str) -> Optional[ConnectionRecord]:
        """Removes a connection from registry."""
        async with self._lock:
            record = self._connections.pop(connection_id, None)
            if record:
                record.is_active = False
                if record.user_id in self._user_connections:
                    self._user_connections[record.user_id].discard(connection_id)
                    if not self._user_connections[record.user_id]:
                        del self._user_connections[record.user_id]

                if record.interview_id in self._interview_connections:
                    self._interview_connections[record.interview_id].discard(connection_id)
                    if not self._interview_connections[record.interview_id]:
                        del self._interview_connections[record.interview_id]
            return record

    async def touch(self, connection_id: str) -> None:
        """Update last_seen timestamp."""
        async with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                conn.touch()

    async def send_message(self, connection_id: str, message: RealtimeMessage) -> bool:
        """Send a structured message to a specific connection."""
        conn = None
        async with self._lock:
            conn = self._connections.get(connection_id)

        if conn and conn.is_active:
            try:
                await conn.websocket.send_text(message.to_json())
                return True
            except Exception:
                await self.remove_connection(connection_id)
                return False
        return False

    async def broadcast_interview(self, interview_id: int, message: RealtimeMessage) -> int:
        """Broadcast a message to all active connections in an interview."""
        cids: List[str] = []
        async with self._lock:
            cids = list(self._interview_connections.get(interview_id, set()))

        sent_count = 0
        for cid in cids:
            if await self.send_message(cid, message):
                sent_count += 1
        return sent_count

    async def get_stale_connections(self, timeout_seconds: float = config.HEARTBEAT_TIMEOUT) -> List[str]:
        """Identify connections that have timed out without heartbeats."""
        now = time.time()
        stale = []
        async with self._lock:
            for cid, conn in self._connections.items():
                if (now - conn.last_seen) > timeout_seconds:
                    stale.append(cid)
        return stale

    async def active_count(self) -> int:
        async with self._lock:
            return len(self._connections)

    async def shutdown(self) -> None:
        """Gracefully close all active WebSocket connections."""
        async with self._lock:
            for conn in list(self._connections.values()):
                try:
                    await conn.websocket.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
            self._connections.clear()
            self._user_connections.clear()
            self._interview_connections.clear()
