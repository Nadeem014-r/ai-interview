"""Phase 9: Skill Scoring, Evidence Aggregation & Confidence Manager.

Maintains per-topic skill scores with bounded exponential smoothing and tracks
independent assessment confidence based on cumulative answer consistency and depth.
"""

from typing import Dict, Any, List, Tuple


class ScoringManager:
    """Manages gradual skill score evolution, confidence tracking, and topic categorization."""

    @staticmethod
    def update_skill_score(
        current_scores: Dict[str, float],
        topic: str,
        eval_score: float,
        alpha: float = 0.6
    ) -> Dict[str, float]:
        """
        Update skill score using weighted exponential smoothing:
        new_score = alpha * eval_score + (1 - alpha) * prev_score
        Guarantees score is bounded in [0.0, 10.0].
        """
        scores = dict(current_scores or {})
        if not topic:
            return scores

        clean_topic = topic.strip()
        clamped_eval = max(0.0, min(10.0, float(eval_score)))

        if clean_topic in scores:
            prev = float(scores[clean_topic])
            updated = (alpha * clamped_eval) + ((1.0 - alpha) * prev)
        else:
            # First observation
            updated = clamped_eval

        scores[clean_topic] = round(max(0.0, min(10.0, updated)), 1)
        return scores

    @staticmethod
    def calculate_confidence(
        topic_observations_count: int,
        evidence_list: List[str],
        has_contradictions: bool = False
    ) -> float:
        """
        Calculate confidence score in [0.1, 1.0].
        Confidence increases with multiple observations and rich concrete evidence.
        Confidence decreases if evidence is sparse or contains contradictions.
        """
        if topic_observations_count <= 0:
            return 0.2

        # Base confidence from number of observations
        base_confidence = min(0.85, 0.4 + (0.15 * topic_observations_count))

        # Evidence bonus
        evidence_count = len(evidence_list or [])
        evidence_factor = min(0.15, evidence_count * 0.05)

        total_confidence = base_confidence + evidence_factor

        # Contradiction / ambiguity penalty
        if has_contradictions:
            total_confidence *= 0.6

        return round(max(0.1, min(1.0, total_confidence)), 2)

    @staticmethod
    def categorize_topics(
        skill_scores: Dict[str, float],
        weak_threshold: float = 5.0,
        strong_threshold: float = 8.0
    ) -> Tuple[List[str], List[str]]:
        """
        Categorize topics into weak and strong lists based on cumulative scores.
        """
        weak_topics = []
        strong_topics = []
        for topic, score in (skill_scores or {}).items():
            if score < weak_threshold:
                if topic not in weak_topics:
                    weak_topics.append(topic)
            elif score >= strong_threshold:
                if topic not in strong_topics:
                    strong_topics.append(topic)
        return weak_topics, strong_topics
