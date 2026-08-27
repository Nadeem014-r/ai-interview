from typing import Dict, Any, Optional
from app.evaluation.rubric import EVALUATION_RUBRIC, get_rubric_weights


class DeterministicScorer:
    """Deterministic, mathematically auditable scorer for interview evaluations."""

    @staticmethod
    def calculate_question_weighted_score(
        correctness: float,
        relevance: float,
        reasoning: float,
        depth: float,
        communication: float,
        question_type: str = "technical"
    ) -> float:
        """Calculate weighted score deterministically from rubric dimension scores (0-10 scale)."""
        weights = get_rubric_weights(question_type)
        c = max(0.0, min(10.0, float(correctness)))
        rel = max(0.0, min(10.0, float(relevance)))
        reas = max(0.0, min(10.0, float(reasoning)))
        d = max(0.0, min(10.0, float(depth)))
        comm = max(0.0, min(10.0, float(communication)))

        weighted = (
            (c * weights.get("correctness", 0.35)) +
            (rel * weights.get("relevance", 0.20)) +
            (reas * weights.get("reasoning", 0.20)) +
            (d * weights.get("depth", 0.15)) +
            (comm * weights.get("communication", 0.10))
        )
        return round(min(10.0, max(0.0, weighted)), 2)

    @staticmethod
    def calculate_overall_interview_score(question_scores: list[float]) -> float:
        """Calculate overall percentage score (0-100 scale) deterministically."""
        if not question_scores:
            return 0.0
        clamped_scores = [max(0.0, min(10.0, float(s))) for s in question_scores]
        avg_score_10 = sum(clamped_scores) / len(clamped_scores)
        return round(avg_score_10 * 10.0, 1)

    @staticmethod
    def classify_answer_quality(overall_score_10: float, is_evasive_or_empty: bool = False) -> str:
        """Categorize answer quality using calibrated score bands."""
        if is_evasive_or_empty or overall_score_10 < 2.0:
            return "i_dont_know" if is_evasive_or_empty else "unanswered"
        elif overall_score_10 < 3.5:
            return "incorrect"
        elif overall_score_10 < 5.0:
            return "weak"
        elif overall_score_10 < 6.8:
            return "partial"
        elif overall_score_10 < 8.2:
            return "good"
        elif overall_score_10 < 9.2:
            return "strong"
        else:
            return "exceptional"
