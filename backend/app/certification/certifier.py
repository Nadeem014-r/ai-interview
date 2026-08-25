"""Phase 10I: Release Certification & Verification Engine.

Aggregates test verdicts across all subsystem categories to produce a machine-readable
and human-readable release certification report.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class CategoryVerdict:
    name: str
    passed: bool
    details: str = ""


class ReleaseCertifier:
    """Evaluates subsystem test results and generates official release certification summaries."""

    def __init__(self):
        self._categories: Dict[str, CategoryVerdict] = {}

    def record_verdict(self, category_name: str, passed: bool, details: str = "Passed all checks.") -> None:
        """Records the pass/fail status for a subsystem certification category."""
        self._categories[category_name] = CategoryVerdict(
            name=category_name,
            passed=passed,
            details=details
        )

    def is_certified(self) -> bool:
        """System is certified only if all recorded categories pass."""
        if not self._categories:
            return False
        return all(v.passed for v in self._categories.values())

    def generate_report(self) -> Dict[str, Any]:
        """Produces a structured machine-readable certification report."""
        certified = self.is_certified()
        matrix = {
            name: {
                "status": "PASS" if verdict.passed else "FAIL",
                "details": verdict.details
            }
            for name, verdict in self._categories.items()
        }

        return {
            "release_certification": "CERTIFIED" if certified else "NOT_CERTIFIED",
            "total_categories_evaluated": len(self._categories),
            "passed_categories": sum(1 for v in self._categories.values() if v.passed),
            "failed_categories": sum(1 for v in self._categories.values() if not v.passed),
            "matrix": matrix
        }

    def print_text_summary(self) -> str:
        """Produces a human-readable text matrix."""
        rep = self.generate_report()
        lines = [
            "============================================================",
            "             PHASE 10I SYSTEM RELEASE CERTIFICATION         ",
            "============================================================"
        ]
        for name, data in rep["matrix"].items():
            lines.append(f"{name.ljust(30, '.')} {data['status']}")
        lines.append("------------------------------------------------------------")
        lines.append(f"OVERALL STATUS: {rep['release_certification']}")
        lines.append("============================================================")
        return "\n".join(lines)


# Global certification evaluator
certifier = ReleaseCertifier()
