"""Bounded access to CPU-heavy local inference engines.

Kokoro synthesis and Whisper transcription both run on the CPU, dispatched
through ``asyncio.to_thread``. That executor will happily run roughly
``cpu_count + 4`` of them at once, so N simultaneous candidates meant N
concurrent inference jobs competing for the same cores. The failure mode is not
graceful: every job slows in proportion, and past a handful they all exceed
their request timeouts, so a busy minute becomes a minute of failed
transcriptions and questions the interviewer never speaks.

Providers that own such an engine expose ``inference_slot()`` returning an
asyncio.Semaphore. This helper wraps it so callers can write one ``async with``
that also works for providers with no bound to apply -- a cloud STT/TTS
provider, or a test double -- which simply proceed immediately.
"""

import asyncio
import inspect
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


@asynccontextmanager
async def inference_slot(provider: Any) -> AsyncIterator[None]:
    """Hold one of the provider's inference slots for the duration of the block.

    Providers without an ``inference_slot`` are unbounded by design (a network
    call costs this machine nothing to run concurrently), so they yield at once.
    The slot is always released, including when the caller is cancelled -- a
    candidate closing the tab must not leak a permit and shrink the pool.
    """
    getter = getattr(provider, "inference_slot", None)
    if not callable(getter):
        yield
        return

    try:
        semaphore = getter()
    except RuntimeError:
        # No running loop to bind a semaphore to. Nothing to bound; proceed.
        yield
        return

    if not isinstance(semaphore, asyncio.Semaphore):
        # A test double, or a provider returning something else entirely.
        # Bounding is an optimisation, never a correctness requirement, so an
        # unrecognised object must not fail or stall the call.
        yield
        return

    await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()
