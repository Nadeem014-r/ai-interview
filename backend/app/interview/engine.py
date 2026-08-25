"""Phase 9: Adaptive Interview Engine Orchestrator.

Coordinates interview lifecycle, planning, evaluation ingestion, skill evolution,
follow-up intelligence, difficulty adaptation, and time-aware stop conditions.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Interview, InterviewState, Question, Answer, Role
from app.interview.timer import InterviewTimer
from app.interview.state_machine import AdaptiveStateMachine
from app.interview.question_selector import QuestionSelector
from app.interview.planner import InterviewPlanner
from app.interview.conversation import FollowUpEngine
from app.interview.scoring import ScoringManager


class AdaptiveInterviewEngine:
    """Master coordinator for adaptive, human-like interview turns."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.question_selector = QuestionSelector(db)

    async def initialize_interview_state(
        self,
        interview: Interview,
        key_topics: List[str],
        initial_question_id: Optional[int] = None
    ) -> InterviewState:
        """
        Constructs initial interview state informed by the InterviewPlanner.
        """
        # Fetch role details if needed
        req_skills: List[str] = []
        stmt_role = select(Role).where(Role.id == interview.role_id)
        res_role = await self.db.execute(stmt_role)
        role = res_role.scalars().first()
        if role:
            req_skills = role.required_skills or []

        # Create structured plan
        plan = InterviewPlanner.plan_interview(
            role_title=role.title if role else "Software Engineer",
            key_topics=key_topics or (role.key_topics if role else []),
            required_skills=req_skills,
            candidate_level=interview.target_level,
            interview_type=interview.interview_type,
            duration_minutes=interview.duration_minutes
        )

        all_planned_topics = plan["primary_topics"] + plan["secondary_topics"]
        first_topic = all_planned_topics[0] if all_planned_topics else "General Computer Science"
        duration_seconds = max(1, interview.duration_minutes) * 60

        initial_state = InterviewState(
            interview_id=interview.id,
            current_topic=first_topic,
            difficulty="medium",
            time_remaining_seconds=duration_seconds,
            questions_asked_count=0,
            current_question_id=initial_question_id,
            skill_scores={},
            weak_topics=[],
            strong_topics=[],
            covered_topics=[],
            remaining_topics=all_planned_topics[1:] if len(all_planned_topics) > 1 else [],
            interview_stage="intro"
        )
        self.db.add(initial_state)
        await self.db.commit()
        await self.db.refresh(initial_state)
        return initial_state

    async def get_current_state(self, interview_id: int) -> Optional[InterviewState]:
        """Fetch active state for interview."""
        stmt = select(InterviewState).where(InterviewState.interview_id == interview_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def process_answer_turn(
        self,
        interview: Interview,
        state: InterviewState,
        last_eval_score: float,
        asked_question_ids: List[int],
        last_eval_dict: Optional[Dict[str, Any]] = None,
        last_answer_text: Optional[str] = None
    ) -> Tuple[InterviewState, Optional[Question], bool]:
        """
        Processes a candidate's answer turn:
        1. Updates remaining time.
        2. Checks stop conditions.
        3. Evaluates follow-up decision (probes deeper if vague or very strong).
        4. Or advances topic and adapts difficulty.
        5. Selects next question and updates state.
        """
        # 1. Update timer
        remaining_sec = InterviewTimer.calculate_remaining_seconds(
            interview.start_time or datetime.utcnow(),
            interview.duration_minutes
        )
        state.time_remaining_seconds = remaining_sec
        state.questions_asked_count += 1

        total_duration_sec = interview.duration_minutes * 60
        target_max_turns = 8 if interview.duration_minutes >= 45 else (5 if interview.duration_minutes >= 25 else 3)

        # 2. Check Stop Conditions
        is_completed = False
        if (
            remaining_sec <= 0
            or state.questions_asked_count >= target_max_turns
            or not InterviewTimer.has_sufficient_time_for_turn(remaining_sec, min_seconds=90)
        ):
            state.interview_stage = "wrapup"
            state.current_question_id = None
            interview.status = "completed"
            interview.end_time = datetime.utcnow()
            is_completed = True
            await self.db.commit()
            return state, None, is_completed

        # 3. Determine if a targeted conversational follow-up probe is warranted
        depth_score = float(last_eval_dict.get("depth_score", 7.0)) if last_eval_dict else 7.0
        evidence_list = last_eval_dict.get("evidence", []) if last_eval_dict else []
        
        # Count consecutive questions on current topic
        turn_count_on_topic = 1 + state.covered_topics.count(state.current_topic)
        should_follow_up, reason_cat = FollowUpEngine.should_follow_up(
            last_eval_score=last_eval_score,
            evidence=evidence_list,
            depth_score=depth_score,
            turn_count_on_topic=turn_count_on_topic,
            time_remaining_seconds=remaining_sec
        )

        next_question: Optional[Question] = None

        if should_follow_up:
            # Generate or select a follow-up question
            state.interview_stage = "adaptive_probe" if last_eval_score < 7.0 else "deep_dive"
            
            # Fetch previous question text
            prev_q_text = f"Questions regarding {state.current_topic}"
            if state.current_question_id:
                stmt_prev_q = select(Question).where(Question.id == state.current_question_id)
                res_prev_q = await self.db.execute(stmt_prev_q)
                prev_q_obj = res_prev_q.scalars().first()
                if prev_q_obj and hasattr(prev_q_obj, 'question_text') and prev_q_obj.question_text:
                    prev_q_text = prev_q_obj.question_text

            follow_up_data = await FollowUpEngine.generate_adaptive_follow_up(
                topic=state.current_topic,
                question_text=prev_q_text,
                candidate_answer=last_answer_text or "",
                eval_feedback=last_eval_dict.get("feedback_text", "") if last_eval_dict else "",
                reason_category=reason_cat,
                target_level=interview.target_level
            )

            # Persist follow-up question
            next_question = Question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=state.current_topic,
                difficulty=state.difficulty,
                question_type="technical" if interview.interview_type == "technical" else interview.interview_type,
                question_text=follow_up_data.get("question_text", f"Can you dive deeper into {state.current_topic}?"),
                expected_concepts=follow_up_data.get("expected_concepts", [state.current_topic]),
                follow_ups=follow_up_data.get("follow_ups", [])
            )
            self.db.add(next_question)
            await self.db.commit()
            await self.db.refresh(next_question)

            # Update scores slightly for initial probe
            state.skill_scores = ScoringManager.update_skill_score(
                state.skill_scores or {}, state.current_topic, last_eval_score
            )
            state.weak_topics, state.strong_topics = ScoringManager.categorize_topics(state.skill_scores)

        else:
            # 4. Standard Competency Advance & Gradual Difficulty Adaptation
            state.interview_stage = AdaptiveStateMachine.determine_next_stage(
                state.questions_asked_count,
                remaining_sec,
                total_duration_sec,
                interview_type=interview.interview_type
            )

            # Mark current topic covered
            if state.current_topic and state.current_topic not in state.covered_topics:
                state.covered_topics.append(state.current_topic)
                if state.current_topic in state.remaining_topics:
                    state.remaining_topics.remove(state.current_topic)

            next_diff, next_topic, skill_scores, weak, strong = AdaptiveStateMachine.adapt_difficulty_and_topic(
                current_difficulty=state.difficulty,
                last_eval_score=last_eval_score,
                current_topic=state.current_topic,
                covered_topics=state.covered_topics,
                remaining_topics=state.remaining_topics,
                skill_scores=state.skill_scores or {},
                weak_topics=state.weak_topics or [],
                strong_topics=state.strong_topics or []
            )

            state.difficulty = next_diff
            state.current_topic = next_topic
            state.skill_scores = skill_scores
            state.weak_topics = weak
            state.strong_topics = strong

            # Select next question
            next_question = await self.question_selector.select_or_generate_question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=next_topic,
                difficulty=next_diff,
                asked_question_ids=asked_question_ids,
                interview_type=interview.interview_type
            )

        state.current_question_id = next_question.id if next_question else None
        await self.db.commit()
        await self.db.refresh(state)
        return state, next_question, False
