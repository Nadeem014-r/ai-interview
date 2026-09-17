"""Concurrent candidates must not create unbounded CPU inference jobs.

Kokoro synthesis and Whisper transcription are CPU-bound and dispatched via
asyncio.to_thread, whose executor runs roughly cpu_count+4 of them at once.
N simultaneous candidates therefore meant N concurrent inference jobs on the
same cores, which does not degrade gracefully: each slows in proportion until
they all breach their request timeouts, so load itself becomes the cause of
failed transcriptions and questions the interviewer never speaks.
"""

import asyncio
import pytest

from app.providers.config import TTS_MAX_CONCURRENCY, STT_MAX_CONCURRENCY
from app.voice.concurrency import inference_slot


class _Tracking:
    """Provider double that records how many jobs overlap inside a slot."""

    def __init__(self, limit: int):
        self._sem_limit = limit
        self._sem = None
        self.live = 0
        self.peak = 0

    def inference_slot(self):
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._sem_limit)
        return self._sem

    async def work(self, seconds: float = 0.05):
        async with inference_slot(self):
            self.live += 1
            self.peak = max(self.peak, self.live)
            try:
                await asyncio.sleep(seconds)
            finally:
                self.live -= 1


@pytest.mark.asyncio
async def test_slot_caps_simultaneous_jobs():
    provider = _Tracking(limit=2)
    await asyncio.gather(*(provider.work() for _ in range(12)))
    assert provider.peak <= 2, f"{provider.peak} jobs ran at once against a bound of 2"
    assert provider.live == 0, "a permit was leaked"


@pytest.mark.asyncio
async def test_all_queued_work_completes():
    """Bounding must delay work, never drop it."""
    provider = _Tracking(limit=2)
    done = []

    async def job(i):
        await provider.work(0.01)
        done.append(i)

    await asyncio.wait_for(asyncio.gather(*(job(i) for i in range(20))), timeout=15)
    assert sorted(done) == list(range(20))


@pytest.mark.asyncio
async def test_cancelled_caller_releases_its_permit():
    """A candidate closing the tab must not shrink the pool permanently."""
    provider = _Tracking(limit=1)

    task = asyncio.create_task(provider.work(5.0))
    await asyncio.sleep(0.05)          # let it take the only permit
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The permit must be back: this would hang forever if it leaked.
    await asyncio.wait_for(provider.work(0.01), timeout=3)
    assert provider.live == 0


@pytest.mark.asyncio
async def test_tts_and_stt_bounds_are_independent():
    """A queue of one engine's work must not stall the other engine."""
    tts = _Tracking(limit=1)
    stt = _Tracking(limit=1)

    hog = asyncio.create_task(tts.work(1.5))
    await asyncio.sleep(0.05)
    # STT has its own bound, so this must not wait on the TTS queue.
    await asyncio.wait_for(stt.work(0.01), timeout=0.5)
    hog.cancel()
    with pytest.raises(asyncio.CancelledError):
        await hog


@pytest.mark.asyncio
async def test_provider_without_a_bound_is_not_blocked():
    """Cloud providers cost this machine nothing to run concurrently."""

    class Unbounded:
        def __init__(self):
            self.live = 0
            self.peak = 0

        async def work(self):
            async with inference_slot(self):
                self.live += 1
                self.peak = max(self.peak, self.live)
                await asyncio.sleep(0.02)
                self.live -= 1

    p = Unbounded()
    await asyncio.gather(*(p.work() for _ in range(8)))
    assert p.peak == 8, "an unbounded provider was serialised anyway"


@pytest.mark.asyncio
async def test_real_providers_expose_a_bounded_slot():
    """The shipped providers must actually carry a bound."""
    from app.providers.kokoro_tts import KokoroTTSProvider
    from app.providers.whisper_stt import WhisperSmallSTTProvider

    tts_sem = KokoroTTSProvider.inference_slot()
    stt_sem = WhisperSmallSTTProvider.inference_slot()
    assert isinstance(tts_sem, asyncio.Semaphore)
    assert isinstance(stt_sem, asyncio.Semaphore)
    assert tts_sem is not stt_sem, "engines must not share one bound"
    # Same loop asks twice, same semaphore -- otherwise the bound means nothing.
    assert KokoroTTSProvider.inference_slot() is tts_sem
    assert TTS_MAX_CONCURRENCY >= 1 and STT_MAX_CONCURRENCY >= 1
