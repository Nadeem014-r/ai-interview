"""One line of interviewer speech is synthesised once, not once per asker.

The same text is requested more than once in normal use: the countdown
pre-synthesises question one while the interview room asks for it again, the
answer turn warms the next question before the room requests it, a candidate
presses "listen again", and a request is retried after a network blip. Each of
those used to run Kokoro from scratch on the CPU, competing with the
transcription of somebody's answer for the same cores.
"""

import asyncio
import pytest

from app.voice import tts_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    tts_cache.clear()
    yield
    tts_cache.clear()


@pytest.mark.asyncio
async def test_concurrent_requests_for_one_line_share_a_single_synthesis():
    calls = {"n": 0}

    async def produce():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return b"RIFF-audio"

    results = await asyncio.gather(*(
        tts_cache.synthesize_once("Tell me about yourself.", "en_us_female_senior", produce)
        for _ in range(6)
    ))

    assert calls["n"] == 1, f"one line was synthesised {calls['n']} times"
    assert all(r == b"RIFF-audio" for r in results)


@pytest.mark.asyncio
async def test_second_request_is_served_from_cache():
    calls = {"n": 0}

    async def produce():
        calls["n"] += 1
        return b"RIFF-audio"

    await tts_cache.synthesize_once("Line one.", "v1", produce)
    again = await tts_cache.synthesize_once("Line one.", "v1", produce)
    assert calls["n"] == 1
    assert again == b"RIFF-audio"


@pytest.mark.asyncio
async def test_voice_is_part_of_the_key():
    """Two voices are two different recordings; one must not serve the other."""

    async def a():
        return b"voice-a"

    async def b():
        return b"voice-b"

    assert await tts_cache.synthesize_once("Same words.", "voice_a", a) == b"voice-a"
    assert await tts_cache.synthesize_once("Same words.", "voice_b", b) == b"voice-b"


@pytest.mark.asyncio
async def test_failures_are_not_cached_and_reach_every_waiter():
    calls = {"n": 0}

    async def failing():
        calls["n"] += 1
        await asyncio.sleep(0.02)
        raise RuntimeError("engine offline")

    out = await asyncio.gather(*(
        tts_cache.synthesize_once("Flaky line.", "v1", failing) for _ in range(4)
    ), return_exceptions=True)
    assert all(isinstance(o, RuntimeError) for o in out), out
    assert calls["n"] == 1, "the shared failure should not have been retried per waiter"

    # Nothing cached, so a later caller may succeed.
    async def ok():
        return b"recovered"

    assert await tts_cache.synthesize_once("Flaky line.", "v1", ok) == b"recovered"


@pytest.mark.asyncio
async def test_one_waiter_cancelling_does_not_break_the_others():
    started = asyncio.Event()

    async def slow():
        started.set()
        await asyncio.sleep(0.3)
        return b"audio"

    first = asyncio.create_task(tts_cache.synthesize_once("Shared.", "v1", slow))
    await started.wait()
    second = asyncio.create_task(tts_cache.synthesize_once("Shared.", "v1", slow))
    await asyncio.sleep(0.05)

    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second

    assert await asyncio.wait_for(first, timeout=3) == b"audio"


@pytest.mark.asyncio
async def test_cache_is_bounded():
    async def produce():
        return b"x" * 16

    for i in range(tts_cache.MAX_ENTRIES + 25):
        await tts_cache.synthesize_once(f"line {i}", "v1", produce)

    assert tts_cache.stats()["entries"] <= tts_cache.MAX_ENTRIES
    assert tts_cache.stats()["inflight"] == 0, "in-flight entries leaked"


@pytest.mark.asyncio
async def test_prefetched_line_is_then_served_without_resynthesis():
    """The turn warms a line; the room's later request must not re-synthesise."""
    calls = {"n": 0}

    async def produce():
        calls["n"] += 1
        await asyncio.sleep(0.02)
        return b"next-question-audio"

    # The answer turn's prefetch.
    await tts_cache.synthesize_once("What happens on a cache miss?", "en_us_female_senior", produce)
    # The room asking for the very same line a moment later.
    audio = await tts_cache.synthesize_once("What happens on a cache miss?", "en_us_female_senior", produce)

    assert calls["n"] == 1
    assert audio == b"next-question-audio"
