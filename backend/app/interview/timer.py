"""Phase 9: Interview Timer & Boundary Enforcement.

Calculates remaining session time, enforces strictly non-negative time boundaries,
and evaluates remaining turn budgets.
"""

from datetime import datetime, timedelta
from typing import Optional


class InterviewTimer:
    """Provides robust time calculation with zero-boundary enforcement."""

    @staticmethod
    def calculate_remaining_seconds(start_time: Optional[datetime], duration_minutes: int) -> int:
        """
        Calculates remaining seconds in the interview.
        Guarantees returned integer is >= 0 and never negative.
        """
        duration_sec = max(1, duration_minutes or 30) * 60
        if not start_time:
            return duration_sec

        # Handle timezone-aware or naive datetimes consistently
        now = datetime.utcnow()
        if start_time.tzinfo is not None:
            # If start_time has tzinfo, use naive UTC for comparison
            start_naive = start_time.replace(tzinfo=None)
        else:
            start_naive = start_time

        elapsed = (now - start_naive).total_seconds()
        remaining = duration_sec - elapsed
        return max(0, int(remaining))

    @staticmethod
    def is_expired(start_time: Optional[datetime], duration_minutes: int) -> bool:
        """Returns True if the interview duration has completely elapsed."""
        return InterviewTimer.calculate_remaining_seconds(start_time, duration_minutes) <= 0

    @staticmethod
    def has_sufficient_time_for_turn(remaining_seconds: int, min_seconds: int = 90) -> bool:
        """Determines if enough time remains to ask and evaluate another meaningful question."""
        return remaining_seconds >= min_seconds
