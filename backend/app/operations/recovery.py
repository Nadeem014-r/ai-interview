"""Phase 10H: Disaster Recovery & Continuity Policy.

Defines target Recovery Time Objectives (RTO), Recovery Point Objectives (RPO), and automated degradation recovery paths.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class RecoveryTargets:
    """Configurable Recovery Objectives in seconds."""
    RTO_REDIS_LOSS_SEC: float = 5.0          # Fallback to memory/db instantly
    RTO_DATABASE_FAILOVER_SEC: float = 30.0  # Read replica / pool reconnect
    RTO_AI_PROVIDER_FAILOVER_SEC: float = 2.0 # Fast cascade to secondary provider
    RPO_INTERVIEW_STATE_SEC: float = 0.0     # Zero data loss on completed turns
    RPO_AUDIO_RECORDINGS_SEC: float = 5.0    # Local audio buffer flush


class DisasterRecoveryPolicy:
    """Provides operational guidance and health recovery evaluations for outages."""

    @staticmethod
    def get_recovery_targets() -> Dict[str, Any]:
        targets = RecoveryTargets()
        return {
            "rto_targets_seconds": {
                "redis_loss": targets.RTO_REDIS_LOSS_SEC,
                "database_failover": targets.RTO_DATABASE_FAILOVER_SEC,
                "ai_provider_failover": targets.RTO_AI_PROVIDER_FAILOVER_SEC
            },
            "rpo_targets_seconds": {
                "interview_state": targets.RPO_INTERVIEW_STATE_SEC,
                "audio_recordings": targets.RPO_AUDIO_RECORDINGS_SEC
            },
            "dr_strategies": {
                "redis_down": "Auto-degrade to local in-memory store; persist session state in PostgreSQL.",
                "ai_provider_down": "Auto-cascade from primary ElevenLabs/Gemini to FallbackTTS / MockProvider.",
                "database_down": "Reject new interview starts with 503; queue active in-flight turn completions."
            }
        }
