"""Phase 9: Interview Planner & Strategy Constructor.

Constructs deterministic, competency-based interview plans tailored to
role requirements, required skills, candidate level, interview type, and duration.
"""

from typing import List, Dict, Any, Optional


class InterviewPlanner:
    """Constructs structured interview plans and topic sequences."""

    @staticmethod
    def plan_interview(
        role_title: str,
        key_topics: List[str],
        required_skills: List[str],
        candidate_level: str = "entry",
        interview_type: str = "technical",
        duration_minutes: int = 30,
        resume_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a structured plan for the interview session.
        Returns:
            {
                "target_question_count": int,
                "stages": List[str],
                "primary_topics": List[str],
                "secondary_topics": List[str],
                "planned_competencies": List[Dict[str, Any]],
                "focus_area": str
            }
        """
        level = (candidate_level or "entry").lower()
        itype = (interview_type or "technical").lower()
        duration = max(5, duration_minutes or 30)

        # 1. Determine target question count based on duration
        if duration <= 15:
            target_question_count = 3
            stages = ["intro", "core", "deep_dive", "wrapup"]
        elif duration <= 30:
            target_question_count = 5
            stages = ["intro", "warmup", "core", "deep_dive", "resume_discussion", "wrapup"]
        elif duration <= 45:
            target_question_count = 7
            stages = ["intro", "warmup", "core", "deep_dive", "adaptive_probe", "resume_discussion", "behavioral", "wrapup"]
        else:
            target_question_count = 8
            stages = ["intro", "warmup", "core", "deep_dive", "adaptive_probe", "resume_discussion", "behavioral", "wrapup"]

        # Adjust stages for non-technical interview types
        if itype in ["hr", "behavioral"]:
            stages = [s for s in stages if s not in ["adaptive_probe", "deep_dive"]]
            if "behavioral" not in stages:
                stages.insert(-1, "behavioral")

        # 2. Extract and organize competencies
        all_topics: List[str] = []
        # Add role-specific key topics first
        for t in (key_topics or []):
            if t and t.strip() and t.strip() not in all_topics:
                all_topics.append(t.strip())

        # Add required skills next
        for s in (required_skills or []):
            if s and s.strip() and s.strip() not in all_topics:
                all_topics.append(s.strip())

        # Default fallbacks if empty
        if not all_topics:
            if itype == "hr":
                all_topics = ["Introduction & Motivation", "Strengths & Weaknesses", "Career Goals", "Company Alignment"]
            elif itype == "behavioral":
                all_topics = ["Teamwork & Collaboration", "Conflict Resolution", "Ownership & Leadership", "Handling Failure"]
            else:
                all_topics = ["Data Structures & Algorithms", "System Design", "Database Optimization", "API Design & Concurrency"]

        # Split into primary and secondary
        mid_point = max(1, len(all_topics) // 2)
        primary_topics = all_topics[:max(2, mid_point)]
        secondary_topics = all_topics[max(2, mid_point):]

        # 3. Build competency roadmap
        planned_competencies = []
        for idx, topic in enumerate(all_topics):
            priority = "high" if idx < len(primary_topics) else "medium"
            depth = "architectural" if level == "senior" else ("practical" if level == "mid" else "conceptual")
            planned_competencies.append({
                "topic": topic,
                "priority": priority,
                "expected_depth": depth,
                "tested": False
            })

        return {
            "role_title": role_title,
            "target_level": level,
            "interview_type": itype,
            "duration_minutes": duration,
            "target_question_count": target_question_count,
            "stages": stages,
            "primary_topics": primary_topics,
            "secondary_topics": secondary_topics,
            "planned_competencies": planned_competencies,
            "focus_area": f"{level.capitalize()} {itype.capitalize()} for {role_title}"
        }
