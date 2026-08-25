"""Phase 10B: Realtime Session State Machine & Manager.

Manages isolated realtime session states, monotonic sequence tracking,
TTL expiration, and state synchronization across Redis and in-memory stores.
"""

import time
import json
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

from app.realtime.config import config
from app.realtime.redis_store import RedisStore
from app.realtime.exceptions import InvalidSessionStateError, SessionNotFoundError, SessionExpiredError


class RealtimeSessionState(str, Enum):
    """Permitted states for a realtime interview session."""
    CREATED = "created"
    AUTHENTICATED = "authenticated"
    CONNECTED = "connected"
    ACTIVE = "active"
    RECONNECTING = "reconnecting"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CLOSED = "closed"


# Allowed state transitions graph
VALID_SESSION_TRANSITIONS = {
    RealtimeSessionState.CREATED: {RealtimeSessionState.AUTHENTICATED, RealtimeSessionState.CLOSED, RealtimeSessionState.EXPIRED},
    RealtimeSessionState.AUTHENTICATED: {RealtimeSessionState.CONNECTED, RealtimeSessionState.CLOSED, RealtimeSessionState.EXPIRED},
    RealtimeSessionState.CONNECTED: {RealtimeSessionState.ACTIVE, RealtimeSessionState.RECONNECTING, RealtimeSessionState.CLOSED, RealtimeSessionState.EXPIRED},
    RealtimeSessionState.ACTIVE: {RealtimeSessionState.RECONNECTING, RealtimeSessionState.COMPLETED, RealtimeSessionState.CLOSED, RealtimeSessionState.EXPIRED},
    RealtimeSessionState.RECONNECTING: {RealtimeSessionState.ACTIVE, RealtimeSessionState.CONNECTED, RealtimeSessionState.CLOSED, RealtimeSessionState.EXPIRED},
    RealtimeSessionState.COMPLETED: {RealtimeSessionState.CLOSED},
    RealtimeSessionState.EXPIRED: set(),  # Terminal
    RealtimeSessionState.CLOSED: set(),   # Terminal
}


@dataclass
class RealtimeSession:
    """Represents an isolated realtime interview session."""
    session_id: str
    user_id: int
    interview_id: int
    role: str = "candidate"
    state: RealtimeSessionState = RealtimeSessionState.CREATED
    sequence_number: int = 0
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: RealtimeSessionState) -> None:
        """
        Safely transition to new session state.
        Raises InvalidSessionStateError if transition is illegal.
        """
        if self.state == new_state:
            return

        allowed = VALID_SESSION_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidSessionStateError(f"Illegal session state transition from '{self.state.value}' to '{new_state.value}'.")

        self.state = new_state
        self.last_activity = time.time()

    def update_activity(self) -> None:
        """Touch the last activity timestamp."""
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "interview_id": self.interview_id,
            "role": self.role,
            "state": self.state.value,
            "sequence_number": self.sequence_number,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RealtimeSession":
        return cls(
            session_id=data["session_id"],
            user_id=int(data["user_id"]),
            interview_id=int(data["interview_id"]),
            role=data.get("role", "candidate"),
            state=RealtimeSessionState(data.get("state", "created")),
            sequence_number=int(data.get("sequence_number", 0)),
            created_at=float(data.get("created_at", time.time())),
            last_activity=float(data.get("last_activity", time.time())),
            metadata=data.get("metadata", {})
        )


class RealtimeSessionManager:
    """Manages active realtime sessions with store persistence and TTL enforcement."""

    def __init__(self, store: Optional[RedisStore] = None):
        self.store = store or RedisStore()
        # Fast in-process cache for open websocket sessions
        self._local_sessions: Dict[str, RealtimeSession] = {}

    def _get_key(self, session_id: str) -> str:
        return f"realtime:session:{session_id}"

    async def create_session(
        self,
        user_id: int,
        interview_id: int,
        role: str = "candidate",
        session_id: Optional[str] = None
    ) -> RealtimeSession:
        """Create and persist a new realtime session."""
        sid = session_id or f"sess_{uuid.uuid4().hex}"
        session = RealtimeSession(
            session_id=sid,
            user_id=user_id,
            interview_id=interview_id,
            role=role,
            state=RealtimeSessionState.CREATED
        )
        self._local_sessions[sid] = session
        await self.save_session(session)
        return session

    async def get_session(self, session_id: str) -> Optional[RealtimeSession]:
        """Retrieve a session by ID, validating TTL."""
        if session_id in self._local_sessions:
            session = self._local_sessions[session_id]
            # Check expiration
            if time.time() - session.last_activity > config.SESSION_TTL_SECONDS:
                session.transition_to(RealtimeSessionState.EXPIRED)
                await self.save_session(session)
                return None
            return session

        # Load from store
        raw = await self.store.get(self._get_key(session_id))
        if not raw:
            return None

        try:
            data = json.loads(raw)
            session = RealtimeSession.from_dict(data)
            self._local_sessions[session_id] = session
            return session
        except Exception:
            return None

    async def save_session(self, session: RealtimeSession) -> None:
        """Persist session state to store with TTL."""
        self._local_sessions[session.session_id] = session
        key = self._get_key(session.session_id)
        val = json.dumps(session.to_dict())
        await self.store.set(key, val, ttl_seconds=config.SESSION_TTL_SECONDS)

    async def close_session(self, session_id: str) -> None:
        """Safely close and clean up a session."""
        session = await self.get_session(session_id)
        if session:
            try:
                session.transition_to(RealtimeSessionState.CLOSED)
                await self.save_session(session)
            except InvalidSessionStateError:
                pass
        self._local_sessions.pop(session_id, None)
        await self.store.delete(self._get_key(session_id))
