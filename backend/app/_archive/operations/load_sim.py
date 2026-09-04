"""Phase 10H: Offline Deterministic Load & Stress Simulation Utilities.

Simulates concurrent interviews, burst audio traffic, and provider latencies without real cloud APIs.
"""

import asyncio
from typing import Dict, Any, List, Callable, Awaitable, Optional
from app._archive.operations.metrics import op_metrics


class LoadSimulator:
    """Runs deterministic concurrent load tests in offline environments."""

    @staticmethod
    async def simulate_concurrent_interviews(
        concurrency: int = 10,
        turns_per_interview: int = 3,
        simulated_turn_fn: Optional[Callable[[int, int], Awaitable[bool]]] = None
    ) -> Dict[str, Any]:
        """
        Simulates concurrent interview sessions executing simultaneous audio turns.
        """
        async def _default_turn(cand_id: int, turn_idx: int) -> bool:
            op_metrics.increment_counter("http_requests_total")
            op_metrics.increment_counter("llm_calls_total")
            op_metrics.increment_counter("stt_calls_total")
            op_metrics.increment_counter("tts_calls_total")
            op_metrics.record_timing("http_latency", 25.0 + (turn_idx * 5.0))
            await asyncio.sleep(0.01)
            return True

        turn_worker = simulated_turn_fn or _default_turn

        async def _run_session(cand_id: int):
            op_metrics.increment_counter("interviews_started_total")
            for t in range(turns_per_interview):
                await turn_worker(cand_id, t)
            op_metrics.increment_counter("interviews_completed_total")
            return True

        tasks = [_run_session(i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful

        return {
            "concurrency": concurrency,
            "turns_per_interview": turns_per_interview,
            "total_turns_simulated": concurrency * turns_per_interview,
            "successful_interviews": successful,
            "failed_interviews": failed,
            "is_offline_simulation": True
        }
