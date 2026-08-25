"""Phase 10H: Operational AI Cost & Token Usage Monitoring.

Tracks token consumption, provider utilization, and estimates operational costs per session and daily totals.
"""

import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ProviderPricing:
    """Configurable pricing per 1,000 tokens in USD."""
    input_cost_per_1k: float = 0.0015
    output_cost_per_1k: float = 0.0020


DEFAULT_PRICING: Dict[str, ProviderPricing] = {
    "gemini": ProviderPricing(input_cost_per_1k=0.000125, output_cost_per_1k=0.000375),
    "openai": ProviderPricing(input_cost_per_1k=0.0015, output_cost_per_1k=0.0020),
    "elevenlabs": ProviderPricing(input_cost_per_1k=0.0000, output_cost_per_1k=0.0000),  # Character-based or included
    "mock": ProviderPricing(input_cost_per_1k=0.0, output_cost_per_1k=0.0)
}


class AICostMonitor:
    """Thread-safe operational AI cost and token consumption tracker."""

    def __init__(self, pricing_table: Optional[Dict[str, ProviderPricing]] = None):
        self.pricing = pricing_table or DEFAULT_PRICING
        self._lock = threading.Lock()
        self._provider_usage: Dict[str, Dict[str, Any]] = {}
        self._session_usage: Dict[str, Dict[str, Any]] = {}

    def record_usage(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        session_id: Optional[str] = None,
        is_failure: bool = False
    ) -> float:
        """
        Records token usage for a provider and optional session.
        Returns estimated cost for this specific call in USD.
        """
        pricing = self.pricing.get(provider.lower(), ProviderPricing())
        cost = (
            (input_tokens / 1000.0) * pricing.input_cost_per_1k +
            (output_tokens / 1000.0) * pricing.output_cost_per_1k
        )

        with self._lock:
            # 1. Update Provider Aggregate
            p_data = self._provider_usage.setdefault(provider, {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "failures": 0
            })
            p_data["request_count"] += 1
            p_data["input_tokens"] += input_tokens
            p_data["output_tokens"] += output_tokens
            p_data["total_tokens"] += (input_tokens + output_tokens)
            p_data["estimated_cost_usd"] = round(p_data["estimated_cost_usd"] + cost, 6)
            if is_failure:
                p_data["failures"] += 1

            # 2. Update Session Aggregate if provided
            if session_id:
                s_data = self._session_usage.setdefault(session_id, {
                    "request_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0
                })
                s_data["request_count"] += 1
                s_data["input_tokens"] += input_tokens
                s_data["output_tokens"] += output_tokens
                s_data["total_tokens"] += (input_tokens + output_tokens)
                s_data["estimated_cost_usd"] = round(s_data["estimated_cost_usd"] + cost, 6)

        return round(cost, 6)

    def get_provider_summary(self, provider: str) -> Dict[str, Any]:
        """Retrieves operational stats for a specific provider."""
        with self._lock:
            return dict(self._provider_usage.get(provider, {
                "request_count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "failures": 0
            }))

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Retrieves operational stats for a specific session."""
        with self._lock:
            return dict(self._session_usage.get(session_id, {
                "request_count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0
            }))

    def get_total_cost_usd(self) -> float:
        """Computes all-time total estimated cost in USD."""
        with self._lock:
            return round(sum(p["estimated_cost_usd"] for p in self._provider_usage.values()), 4)


cost_monitor = AICostMonitor()
