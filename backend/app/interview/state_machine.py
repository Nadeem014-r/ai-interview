"""Phase 9: Adaptive State Machine & Progression Engine.

Manages deterministic, human-like interview progression stages, gradual non-oscillating
difficulty adaptation, and intelligent competency/topic transitions.
"""

from typing import Dict, Any, List, Tuple, Optional
from app.interview.scoring import ScoringManager

VALID_STAGES = [
    "intro",
    "warmup",
    "core",
    "deep_dive",
    "adaptive_probe",
    "resume_discussion",
    "behavioral",
    "wrapup"
]


class AdaptiveStateMachine:
    """Manages interview lifecycle stages and adaptive difficulty/topic transitions."""

    @staticmethod
    def determine_next_stage(
        questions_asked: int,
        time_remaining_seconds: int,
        total_duration_seconds: int,
        interview_type: str = "technical"
    ) -> str:
        """
        Determines the appropriate next interview stage based on progress, time, and type.
        """
        itype = (interview_type or "technical").lower()
        duration = max(60, total_duration_seconds or 1800)

        # Wrap-up condition: less than 10% time remaining or <= 90 seconds or hard cap of 25 turns reached
        if time_remaining_seconds <= 90 or time_remaining_seconds < (duration * 0.10) or questions_asked >= 25:
            return "wrapup"

        if questions_asked == 0:
            return "intro"
        elif questions_asked == 1:
            return "warmup"
        elif questions_asked in [2, 3]:
            return "core"
        elif questions_asked in [4, 5]:
            return "deep_dive" if itype == "technical" else "behavioral"
        elif questions_asked == 6:
            return "resume_discussion"
        elif questions_asked in [7, 8]:
            return "behavioral" if itype == "technical" else "core"
        else:
            return "core" if itype == "technical" else "behavioral"

    @staticmethod
    def validate_transition(current_stage: str, next_stage: str) -> bool:
        """
        Verifies that a proposed stage transition is legally permissible.
        Prevents transitioning out of wrapup back into active question stages.
        """
        cur = (current_stage or "intro").lower()
        nxt = (next_stage or "intro").lower()

        if cur == "wrapup" and nxt != "wrapup":
            return False
        return True

    @staticmethod
    def adapt_difficulty_and_topic(
        current_difficulty: str,
        last_eval_score: float,
        current_topic: str,
        covered_topics: List[str],
        remaining_topics: List[str],
        skill_scores: Dict[str, float],
        weak_topics: List[str],
        strong_topics: List[str]
    ) -> Tuple[str, str, Dict[str, float], List[str], List[str]]:
        """
        Adapts difficulty gradually (one step at a time) and selects the next topic.
        - Score >= 8.0: gradual increase (easy->medium->hard)
        - 5.0 <= Score < 8.0: maintain difficulty
        - Score < 5.0: gradual decrease (hard->medium->easy)
        """
        cur_diff = (current_difficulty or "medium").lower()
        clamped_score = max(0.0, min(10.0, float(last_eval_score)))

        # 1. Update skill score using ScoringManager
        updated_skill_scores = ScoringManager.update_skill_score(
            current_scores=skill_scores,
            topic=current_topic,
            eval_score=clamped_score
        )

        # 2. Categorize weak and strong topics based on updated scores
        updated_weak, updated_strong = ScoringManager.categorize_topics(updated_skill_scores)

        # 3. Gradual non-oscillating difficulty adaptation
        next_difficulty = cur_diff
        if clamped_score >= 8.0:
            if cur_diff == "easy":
                next_difficulty = "medium"
            elif cur_diff == "medium":
                next_difficulty = "hard"
            elif cur_diff == "hard":
                next_difficulty = "hard"
        elif clamped_score < 5.0:
            if cur_diff == "hard":
                next_difficulty = "medium"
            elif cur_diff == "medium":
                next_difficulty = "easy"
            elif cur_diff == "easy":
                next_difficulty = "easy"
        else:
            next_difficulty = cur_diff

        # 4. Smart topic selection prioritizing uncovered competencies
        next_topic = current_topic
        if remaining_topics:
            next_topic = remaining_topics[0]
        elif updated_weak:
            # Re-probe a weak competency if all topics were covered
            next_topic = updated_weak[0]
        elif covered_topics:
            next_topic = covered_topics[0]

        return next_difficulty, next_topic, updated_skill_scores, updated_weak, updated_strong
