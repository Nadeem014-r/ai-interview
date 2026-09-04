"""Phase 10F: Request, Session & Turn Correlation ID Context Propagation.

Maintains asynchronous context-local identifiers for tracing operations across distributed components.
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id_ctx", default=None)
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id_ctx", default=None)
_session_id_ctx: ContextVar[Optional[str]] = ContextVar("session_id_ctx", default=None)


class CorrelationContext:
    """Async context manager and accessor for correlation and request IDs."""

    @staticmethod
    def generate_id(prefix: str = "req") -> str:
        """Generates a random, safe identifier."""
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def get_request_id() -> str:
        req_id = _request_id_ctx.get()
        if not req_id:
            req_id = CorrelationContext.generate_id("req")
            _request_id_ctx.set(req_id)
        return req_id

    @staticmethod
    def set_request_id(request_id: str) -> None:
        _request_id_ctx.set(request_id)

    @staticmethod
    def get_correlation_id() -> str:
        corr_id = _correlation_id_ctx.get()
        if not corr_id:
            corr_id = CorrelationContext.generate_id("corr")
            _correlation_id_ctx.set(corr_id)
        return corr_id

    @staticmethod
    def set_correlation_id(correlation_id: str) -> None:
        _correlation_id_ctx.set(correlation_id)

    @staticmethod
    def get_session_id() -> Optional[str]:
        return _session_id_ctx.get()

    @staticmethod
    def set_session_id(session_id: Optional[str]) -> None:
        _session_id_ctx.set(session_id)

    @staticmethod
    def get_context_dict() -> Dict[str, Any]:
        """Returns active correlation context dictionary."""
        return {
            "request_id": CorrelationContext.get_request_id(),
            "correlation_id": CorrelationContext.get_correlation_id(),
            "session_id": CorrelationContext.get_session_id()
        }
