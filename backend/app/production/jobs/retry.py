"""Phase 10C: Exponential Backoff Retry Policy.
"""

import math
from typing import Optional


class ExponentialBackoffPolicy:
    """Calculates exponential backoff delays with jitter suppression for deterministic testing."""

    def __init__(
        self,
        initial_backoff_sec: float = 0.5,
        backoff_factor: float = 2.0,
        max_backoff_sec: float = 30.0
    ):
        self.initial_backoff_sec = initial_backoff_sec
        self.backoff_factor = backoff_factor
        self.max_backoff_sec = max_backoff_sec

    def get_delay_seconds(self, attempt: int) -> float:
        """
        Calculates retry delay for the specified attempt number (1-indexed).
        delay = min(max_backoff, initial_backoff * (backoff_factor ** (attempt - 1)))
        """
        if attempt <= 1:
            return self.initial_backoff_sec
        calculated = self.initial_backoff_sec * (self.backoff_factor ** (attempt - 1))
        return round(min(self.max_backoff_sec, calculated), 3)
