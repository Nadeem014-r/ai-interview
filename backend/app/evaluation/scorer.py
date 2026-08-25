from typing import Dict, Any
from app.evaluation.rubric import EVALUATION_RUBRIC

class DeterministicScorer:
    @staticmethod
    def calculate_question_weighted_score(
        correctness: float,
        relevance: float,
        reasoning: float,
        depth: float,
        communication: float
    ) -> float:
        """Calculate weighted score deterministically from rubric dimension scores (0-10 scale)."""
        weighted = (
            (correctness * EVALUATION_RUBRIC["correctness"]["weight"]) +
            (relevance * EVALUATION_RUBRIC["relevance"]["weight"]) +
            (reasoning * EVALUATION_RUBRIC["reasoning"]["weight"]) +
            (depth * EVALUATION_RUBRIC["depth"]["weight"]) +
            (communication * EVALUATION_RUBRIC["communication"]["weight"])
        )
        return round(min(10.0, max(0.0, weighted)), 2)

    @staticmethod
    def calculate_overall_interview_score(question_scores: list[float]) -> float:
        """Calculate overall percentage score (0-100 scale) deterministically."""
        if not question_scores:
            return 0.0
        avg_score_10 = sum(question_scores) / len(question_scores)
        return round(avg_score_10 * 10.0, 1)
