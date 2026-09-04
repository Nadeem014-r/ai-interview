"""Phase 10H: Operational Runbook Knowledge Engine.

Provides programmatic access to standard operating procedures (SOPs) for site reliability engineering.
"""

from typing import Dict, List, Optional


RUNBOOK_PROCEDURES: Dict[str, Dict[str, str]] = {
    "REDIS_DOWN": {
        "title": "Redis Cache Outage Incident Response",
        "impact": "Degraded realtime pub/sub caching; system automatically falls back to in-memory/DB stores.",
        "steps": (
            "1. Inspect Redis container logs: `docker compose logs redis`\n"
            "2. Verify host memory limits and Redis OOM status.\n"
            "3. Restart service if hung: `docker compose restart redis`\n"
            "4. Verify application readiness recovers to 'healthy'."
        )
    },
    "DATABASE_DOWN": {
        "title": "PostgreSQL Database Outage Incident Response",
        "impact": "New interview registrations and completions fail with 503.",
        "steps": (
            "1. Check Postgres container status: `docker compose ps postgres`\n"
            "2. Verify volume mount disk space: `df -h`\n"
            "3. Restart database: `docker compose restart postgres`\n"
            "4. Check for lock contentions."
        )
    },
    "AI_PROVIDER_FAILURE": {
        "title": "AI Provider Outage (ElevenLabs / Gemini / OpenAI)",
        "impact": "Speech synthesis or question generation errors.",
        "steps": (
            "1. Verify FallbackTTSProvider has automatically engaged.\n"
            "2. Check provider quota status in dashboard.\n"
            "3. Switch PRIMARY provider via environment variable.\n"
            "4. Monitor P95 latency metrics for recovery."
        )
    },
    "HIGH_ERROR_RATE": {
        "title": "HTTP 5xx Error Rate Surge",
        "impact": "Candidate interview disruption.",
        "steps": (
            "1. Review structured error logs: `docker compose logs backend | grep ERROR`\n"
            "2. Inspect recent alert fingerprints via diagnostics endpoint.\n"
            "3. Verify downstream services (DB, Redis, storage)."
        )
    }
}


class OperationalRunbook:
    """Retrieves standard operational runbook procedures."""

    @staticmethod
    def get_procedure(incident_code: str) -> Optional[Dict[str, str]]:
        return RUNBOOK_PROCEDURES.get(incident_code.upper())

    @staticmethod
    def list_all_procedures() -> List[str]:
        return list(RUNBOOK_PROCEDURES.keys())
