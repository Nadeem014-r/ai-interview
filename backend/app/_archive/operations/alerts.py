"""Phase 10H: Operational Alert Engine with Intelligent Deduplication & Cooldowns.

Prevents alert storms by grouping alarms by fingerprint and enforcing cooldown intervals.
"""

import time
import threading
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class OperationalAlert:
    alert_code: str
    severity: AlertSeverity
    message: str
    observed_value: Any
    threshold_value: Any
    fingerprint: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False


class AlertEngine:
    """Manages active alerts, enforces cooldown periods, and suppresses duplicate notifications."""

    def __init__(self, cooldown_seconds: float = 60.0):
        self.cooldown_seconds = cooldown_seconds
        self._alerts_history: List[OperationalAlert] = []
        self._last_emitted_timestamps: Dict[str, float] = {}  # fingerprint -> last_emitted_time
        self._lock = threading.Lock()

    def generate_fingerprint(self, alert_code: str, component: str) -> str:
        return f"{alert_code}:{component}"

    def trigger_alert(
        self,
        alert_code: str,
        severity: AlertSeverity,
        message: str,
        observed_value: Any,
        threshold_value: Any,
        component: str = "core"
    ) -> Optional[OperationalAlert]:
        """
        Emits alert if not currently in cooldown for this fingerprint.
        Returns OperationalAlert if emitted, None if deduplicated.
        """
        fingerprint = self.generate_fingerprint(alert_code, component)
        now = time.monotonic()

        with self._lock:
            last_time = self._last_emitted_timestamps.get(fingerprint, 0.0)
            if (now - last_time) < self.cooldown_seconds:
                # Deduplicated / throttled
                return None

            alert = OperationalAlert(
                alert_code=alert_code,
                severity=severity,
                message=message,
                observed_value=observed_value,
                threshold_value=threshold_value,
                fingerprint=fingerprint,
                timestamp=time.time()
            )
            self._alerts_history.append(alert)
            self._last_emitted_timestamps[fingerprint] = now
            if len(self._alerts_history) > 1000:
                del self._alerts_history[:500]

            return alert

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Exports recent alerts history."""
        with self._lock:
            return [
                {
                    "alert_code": a.alert_code,
                    "severity": a.severity.value,
                    "message": a.message,
                    "observed": a.observed_value,
                    "threshold": a.threshold_value,
                    "timestamp": a.timestamp
                }
                for a in self._alerts_history[-limit:]
            ]


alert_engine = AlertEngine()
