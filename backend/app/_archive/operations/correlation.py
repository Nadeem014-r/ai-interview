"""Phase 10H: Operational Correlation Context Layer.

Provides async task-local context variables for unified end-to-end operation tracing.
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

_req_id_ctx: ContextVar[Optional[str]] = ContextVar("op_req_id", default=None)
_sess_id_ctx: ContextVar[Optional[str]] = ContextVar("op_sess_id", default=None)
_interview_id_ctx: ContextVar[Optional[str]] = ContextVar("op_interview_id", default=None)
_conn_id_ctx: ContextVar[Optional[str]] = ContextVar("op_conn_id", default=None)
_job_id_ctx: ContextVar[Optional[str]] = ContextVar("op_job_id", default=None)


class OperationalCorrelation:
    """Manages asynchronous context identifiers for operations and logging."""

    @staticmethod
    def generate_id(prefix: str = "op") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    @classmethod
    def set_context(
        cls,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        interview_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> None:
        if request_id:
            _req_id_ctx.set(request_id)
        if session_id:
            _sess_id_ctx.set(session_id)
        if interview_id:
            _interview_id_ctx.set(interview_id)
        if connection_id:
            _conn_id_ctx.set(connection_id)
        if job_id:
            _job_id_ctx.set(job_id)

    @classmethod
    def get_context_dict(cls) -> Dict[str, Optional[str]]:
        req_id = _req_id_ctx.get()
        if not req_id:
            req_id = cls.generate_id("req")
            _req_id_ctx.set(req_id)

        return {
            "request_id": req_id,
            "session_id": _sess_id_ctx.get(),
            "interview_id": _interview_id_ctx.get(),
            "connection_id": _conn_id_ctx.get(),
            "job_id": _job_id_ctx.get()
        }
