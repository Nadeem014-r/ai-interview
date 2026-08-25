"""Phase 10B: Realtime WebSocket Authentication & Authorization.

Validates JWT credentials, enforces candidate-to-interview ownership,
and isolates access without modifying existing auth modules.
"""

from typing import Dict, Any, Optional
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Interview, User
from app.realtime.exceptions import WebSocketAuthenticationError, WebSocketAuthorizationError


class RealtimeAuthenticator:
    """Authenticates and authorizes WebSocket connections."""

    @staticmethod
    def authenticate_token(token: Optional[str]) -> Dict[str, Any]:
        """
        Validates JWT token and extracts user identity and role.
        Raises WebSocketAuthenticationError if missing, invalid, or expired.
        """
        if not token or not token.strip():
            raise WebSocketAuthenticationError("Missing authentication token.")

        clean_token = token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        try:
            payload = jwt.decode(clean_token, settings.SECRET_KEY, algorithms=["HS256"])
            sub = payload.get("sub")
            role = payload.get("role", "candidate")
            if sub is None:
                raise WebSocketAuthenticationError("Invalid token: missing subject.")
            return {
                "user_id": int(sub),
                "role": role
            }
        except JWTError as e:
            raise WebSocketAuthenticationError("Authentication token is invalid or expired.", raw_error=e)
        except (ValueError, TypeError) as e:
            raise WebSocketAuthenticationError("Malformed token claims.", raw_error=e)

    @staticmethod
    async def authorize_interview_access(
        user_id: int,
        interview_id: int,
        db: Optional[AsyncSession] = None,
        candidate_id: Optional[int] = None
    ) -> bool:
        """
        Verifies that the authenticated user owns or is assigned to the requested interview.
        If db is provided, performs database verification.
        Raises WebSocketAuthorizationError if access is denied.
        """
        if user_id <= 0 or interview_id <= 0:
            raise WebSocketAuthorizationError("Invalid user or interview identifier.")

        if db is not None:
            stmt_int = select(Interview).where(Interview.id == interview_id)
            res_int = await db.execute(stmt_int)
            interview = res_int.scalars().first()
            if not interview:
                raise WebSocketAuthorizationError(f"Interview {interview_id} not found.")

            if interview.candidate_id != user_id:
                raise WebSocketAuthorizationError(f"User {user_id} is not authorized for interview {interview_id}.")
            return True

        # Offline / standalone verification
        if candidate_id is not None and candidate_id != user_id:
            raise WebSocketAuthorizationError(f"User {user_id} mismatch with candidate {candidate_id}.")
        return True
