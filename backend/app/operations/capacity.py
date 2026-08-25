"""Phase 10H: Operational Capacity Planning & Resource Sizing Estimator.

Computes conservative operational concurrency ceilings based on host CPU, RAM, and provider quotas.
"""

from typing import Dict, Any


class CapacityPlanner:
    """Estimates safe concurrency boundaries for the AI Interviewer platform."""

    @staticmethod
    def estimate_concurrency_ceiling(
        cpu_cores: int = 4,
        ram_gb: float = 8.0,
        ram_per_interview_mb: float = 45.0,
        avg_turn_audio_kb_sec: float = 32.0
    ) -> Dict[str, Any]:
        """
        Calculates estimated concurrent interview capacity and bandwidth requirements.
        All values are clearly labeled as operational estimates.
        """
        # Memory-constrained max interviews (leaving 25% for OS and buffer caches)
        available_ram_mb = (ram_gb * 1024.0) * 0.75
        max_interviews_by_ram = int(available_ram_mb / ram_per_interview_mb)

        # CPU-constrained interviews (assuming ~12 concurrent realtime sessions per core)
        max_interviews_by_cpu = int(cpu_cores * 12)

        safe_recommended_interviews = min(max_interviews_by_ram, max_interviews_by_cpu)
        bandwidth_mbps = (safe_recommended_interviews * avg_turn_audio_kb_sec * 8.0) / 1024.0

        return {
            "is_estimate": True,
            "host_specs": {"cpu_cores": cpu_cores, "ram_gb": ram_gb},
            "estimated_max_concurrent_interviews": safe_recommended_interviews,
            "estimated_network_bandwidth_mbps": round(bandwidth_mbps, 2),
            "estimated_websocket_connections_max": safe_recommended_interviews * 2,
            "recommendation": f"Provision for up to {safe_recommended_interviews} concurrent interview sessions."
        }
