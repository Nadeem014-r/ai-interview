"""Synthesised interviewer lines, kept briefly and synthesised only once.

Two separate problems this solves.

*Duplicate synthesis.* The same line is asked for more than once in normal use:
the countdown pre-synthesises question one while the interview room asks for it
again, a candidate presses "listen again", a request is retried after a network
blip, and any question drawn from the bank recurs across candidates. Each of
those previously ran Kokoro from scratch on the CPU, competing with the
transcription of somebody's answer.

*Visible waiting.* Synthesis cannot start before the question exists, but it
need not wait for the question to travel to the browser and come back. The
answer turn starts synthesis the moment it has the next question text, so by
the time the room asks, the work is done or already running -- and the room's
request joins that same job rather than starting a second one.

Bounded on purpose: a small number of recent lines, held in memory, evicted
oldest-first. Nothing here is durable and nothing here is required -- a miss
simply synthesises as before.
"""

import asyncio
import logging
from collections import OrderedDict
from typing import Awaitable, Callable, Dict, Optional, Tuple

logger = logging.getLogger("ai_interviewer.tts_cache")

# Enough to cover a session's recent questions plus a few concurrent
# interviews, without letting audio accumulate. A 15 s line is ~700 KB, so 64
# entries is a few tens of megabytes at worst.
MAX_ENTRIES = 64

Key = Tuple[str, str]  # (voice_id, text)

_audio: "OrderedDict[Key, bytes]" = OrderedDict()
# The in-flight future is stored with the loop that owns it. A future created
# on one event loop cannot be awaited from another, and the test suite runs
# each case on a fresh loop, so an entry from a dead loop is discarded rather
# than awaited -- which would hang forever.
_inflight: Dict[Key, Tuple["asyncio.AbstractEventLoop", "asyncio.Future[bytes]"]] = {}

# No lock guards the maps below, deliberately. Every critical section here runs
# without an await, so the event loop cannot interleave another coroutine part
# way through one. A module-level asyncio.Lock would additionally bind itself to
# whichever loop first used it and fail on every later one.


def _key(text: str, voice_id: str) -> Key:
    return (voice_id or "", (text or "").strip())


def get(text: str, voice_id: str) -> Optional[bytes]:
    """Return cached audio for this line, refreshing its recency."""
    k = _key(text, voice_id)
    audio = _audio.get(k)
    if audio is not None:
        _audio.move_to_end(k)
    return audio


def _store(k: Key, audio: bytes) -> None:
    _audio[k] = audio
    _audio.move_to_end(k)
    while len(_audio) > MAX_ENTRIES:
        _audio.popitem(last=False)


async def synthesize_once(
    text: str,
    voice_id: str,
    produce: Callable[[], Awaitable[bytes]],
) -> bytes:
    """Return this line's audio, synthesising it at most once at a time.

    Concurrent callers for the same line await one shared synthesis instead of
    starting several. A failure is not cached: it propagates to every waiter,
    and the next caller is free to try again.
    """
    k = _key(text, voice_id)
    loop = asyncio.get_running_loop()

    cached = get(text, voice_id)
    if cached is not None:
        return cached

    entry = _inflight.get(k)
    if entry is not None and entry[0] is loop and not entry[1].done():
        # Someone else on this loop is already synthesising this exact line.
        # shield() keeps this waiter's cancellation from cancelling the shared
        # synthesis that other waiters still depend on.
        return await asyncio.shield(entry[1])

    future: "asyncio.Future[bytes]" = loop.create_future()
    _inflight[k] = (loop, future)

    try:
        audio = await produce()
    except BaseException as exc:
        # Failures are never cached: every waiter sees the error and the next
        # caller may try again.
        if _inflight.get(k) == (loop, future):
            _inflight.pop(k, None)
        if not future.done():
            future.set_exception(exc)
            # Retrieve it so Python does not warn about an unconsumed exception
            # when nobody happened to be waiting.
            future.exception()
        raise

    _store(k, audio)
    if _inflight.get(k) == (loop, future):
        _inflight.pop(k, None)
    if not future.done():
        future.set_result(audio)
    return audio


def stats() -> Dict[str, int]:
    return {"entries": len(_audio), "inflight": len(_inflight)}


def clear() -> None:
    """Drop everything. For tests; never needed in a running server."""
    _audio.clear()
    _inflight.clear()
