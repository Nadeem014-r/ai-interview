"""Phase 10G: Centralized Timeout Governance & Bounded Execution Policy.

Ensures zero unbounded awaits across LLMs, STT/TTS providers, Redis, storage, and background workers.
"""

import asyncio
from dataclasses import dataclass
from typing import TypeVar, Awaitable
from app._archive.hardening.exceptions import TimeoutError

T = TypeVar("T")


@dataclass(frozen=True)
class TimeoutPolicy:
    """Centralized timeout bounds in seconds."""
    AI_LLM_TIMEOUT_SEC: float = 25.0
    AI_STT_TIMEOUT_SEC: float = 15.0
    AI_TTS_TIMEOUT_SEC: float = 10.0
    REDIS_OP_TIMEOUT_SEC: float = 2.5
    STORAGE_OP_TIMEOUT_SEC: float = 15.0
    AUTH_OP_TIMEOUT_SEC: float = 3.0
    DB_READ_TIMEOUT_SEC: float = 5.0
    JOB_EXEC_TIMEOUT_SEC: float = 60.0
    REALTIME_TURN_TIMEOUT_SEC: float = 35.0


default_timeout_policy = TimeoutPolicy()


async def run_with_timeout(
    coro: Awaitable[T],
    timeout_sec: float,
    operation_label: str = "Operation"
) -> T:
    """Executes an async coroutine strictly within the designated timeout bound."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_sec)
    except asyncio.TimeoutError as te:
        raise TimeoutError(
            message=f"{operation_label} timed out after {timeout_sec:.1f}s.",
            internal_details=str(te)
        )
