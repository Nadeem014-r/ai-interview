"""Phase 7/9: Adaptive Interview Engine Orchestrator with Structured Memory.

Coordinates interview lifecycle, planning, evaluation ingestion, skill evolution,
follow-up intelligence, claim tracking, difficulty adaptation, and time-aware stop conditions.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Interview, InterviewState, Question, Answer, Role, Resume
from app.interview.timer import InterviewTimer
from app.interview.state_machine import AdaptiveStateMachine
from app.interview.question_selector import QuestionSelector, is_duplicate_question
from app.interview.planner import InterviewPlanner
from app.interview.conversation import FollowUpEngine
from app.interview.scoring import ScoringManager
from app.interview.memory import InterviewMemory, MemoryManager


class AdaptiveInterviewEngine:
    """Master coordinator for adaptive, memory-aware, human-like interview turns."""

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
        Constructs initial interview state informed by the InterviewPlanner and Resume Profile.
        """
        # Fetch role details if needed
        req_skills: List[str] = []
        stmt_role = select(Role).where(Role.id == interview.role_id)
        res_role = await self.db.execute(stmt_role)
        role = res_role.scalars().first()
        if role and isinstance(role, Role):
            req_skills = role.required_skills or []

        # Create structured plan
        plan = InterviewPlanner.plan_interview(
            role_title=role.title if (role and isinstance(role, Role)) else "Software Engineer",
            key_topics=key_topics or ((role.key_topics if isinstance(role, Role) else []) if role else []),
            required_skills=req_skills,
            candidate_level=interview.target_level,
            interview_type=interview.interview_type,
            duration_minutes=interview.duration_minutes
        )

        all_planned_topics = plan["primary_topics"] + plan["secondary_topics"]
        
        # If an initial question was already created (e.g. warmup/intro), align topic with it
        first_topic = all_planned_topics[0] if all_planned_topics else "General Computer Science"
        if initial_question_id:
            stmt_init_q = select(Question).where(Question.id == initial_question_id)
            res_init_q = await self.db.execute(stmt_init_q)
            init_q = res_init_q.scalars().first()
            if init_q and hasattr(init_q, "topic") and init_q.topic:
                first_topic = init_q.topic

        duration_seconds = max(1, interview.duration_minutes) * 60

        initial_state = InterviewState(
            interview_id=interview.id,
            current_topic=first_topic,
            difficulty="easy" if first_topic == "Introduction & Motivation" else "medium",
            time_remaining_seconds=duration_seconds,
            questions_asked_count=0,
            current_question_id=initial_question_id,
            skill_scores={},
            weak_topics=[],
            strong_topics=[],
            covered_topics=[],
            remaining_topics=[t for t in all_planned_topics if t != first_topic],
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

    async def build_interview_memory(
        self,
        interview: Interview,
        state: InterviewState
    ) -> InterviewMemory:
        """Constructs or reconstructs structured InterviewMemory from persisted turns and resume."""
        # 1. Fetch resume profile
        resume_profile = None
        if interview.candidate_id:
            stmt_res = (
                select(Resume)
                .options(selectinload(Resume.resume_profile))
                .where(Resume.user_id == interview.candidate_id)
                .order_by(Resume.created_at.desc())
            )
            res_res = await self.db.execute(stmt_res)
            cand_resume = res_res.scalars().first()
            if isinstance(cand_resume, Resume) and getattr(cand_resume, 'resume_profile', None):
                resume_profile = cand_resume.resume_profile

        # 2. Build initial memory base
        planned_topics = (state.covered_topics or []) + (state.remaining_topics or [])
        memory = MemoryManager.build_initial_memory(
            interview_id=interview.id,
            role_key_topics=planned_topics,
            resume_profile=resume_profile
        )

        # 3. Replay historical answers into memory
        stmt_answers = (
            select(Answer)
            .options(selectinload(Answer.question), selectinload(Answer.evaluation))
            .where(Answer.interview_id == interview.id)
            .order_by(Answer.created_at.asc())
        )
        res_answers = await self.db.execute(stmt_answers)
        for a in res_answers.scalars().all():
            q_text = a.question.question_text if (hasattr(a, 'question') and a.question) else "Question"
            q_topic = a.question.topic if (hasattr(a, 'question') and a.question) else state.current_topic
            ev_dict = {}
            if hasattr(a, 'evaluation') and a.evaluation:
                ev_dict = {
                    "overall_question_score": a.evaluation.overall_question_score,
                    "depth_score": a.evaluation.depth_score,
                    "evidence": a.evaluation.evidence or [],
                    "feedback_text": a.evaluation.feedback_text or "",
                    "demonstrated_concepts": [q_topic],
                    "missing_concepts": [],
                    "misconceptions": []
                }
            MemoryManager.ingest_turn(
                memory=memory,
                question_text=q_text,
                candidate_answer=a.candidate_answer_text or "",
                eval_dict=ev_dict,
                topic=q_topic
            )

        return memory

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
        3. Ingests answer and extracts claims into structured InterviewMemory.
        4. Evaluates follow-up decision (probes deeper on claims/vague/strong answers).
        5. Advances topic with resume and memory context.
        6. Selects next question and updates state.
        """
        # 1. Update timer
        remaining_sec = InterviewTimer.calculate_remaining_seconds(
            interview.start_time or datetime.utcnow(),
            interview.duration_minutes
        )
        state.time_remaining_seconds = remaining_sec
        state.questions_asked_count += 1

        total_duration_sec = max(1, interview.duration_minutes) * 60
        all_topics_covered = bool(
            state.covered_topics
            and not state.remaining_topics
            and len(state.covered_topics) >= 3
            and state.questions_asked_count >= 6
        )

        # 2. Check Stop Conditions
        is_completed = False
        termination_reason = None
        if remaining_sec <= 0:
            is_completed = True
            termination_reason = "time_exhausted"
        elif not InterviewTimer.has_sufficient_time_for_turn(remaining_sec, min_seconds=90):
            is_completed = True
            termination_reason = "insufficient_time_remaining"
        elif all_topics_covered:
            is_completed = True
            termination_reason = "competencies_fully_covered"
        elif state.questions_asked_count >= 25:
            is_completed = True
            termination_reason = "max_session_turns_reached"

        if is_completed:
            state.interview_stage = "wrapup"
            state.current_question_id = None
            interview.status = "completed"
            interview.end_time = datetime.utcnow()
            await self.db.commit()
            return state, None, is_completed

        # 3. Build / Ingest Structured Interview Memory
        memory = await self.build_interview_memory(interview, state)

        # Ingest current turn if not yet recorded
        prev_q_text = f"Questions regarding {state.current_topic}"
        if state.current_question_id:
            stmt_prev_q = select(Question).where(Question.id == state.current_question_id)
            res_prev_q = await self.db.execute(stmt_prev_q)
            prev_q_obj = res_prev_q.scalars().first()
            if prev_q_obj and hasattr(prev_q_obj, 'question_text') and prev_q_obj.question_text:
                prev_q_text = prev_q_obj.question_text

        if last_answer_text:
            MemoryManager.ingest_turn(
                memory=memory,
                question_text=prev_q_text,
                candidate_answer=last_answer_text,
                eval_dict=last_eval_dict or {},
                topic=state.current_topic or "Technical"
            )

        asked_texts = list(memory.asked_question_texts)
        if asked_question_ids:
            stmt_asked = select(Question.question_text).where(Question.id.in_(asked_question_ids))
            res_asked = await self.db.execute(stmt_asked)
            for row in res_asked.all():
                if row[0] and row[0] not in asked_texts:
                    asked_texts.append(row[0])

        # 4. Adaptive Difficulty Progression
        cur_diff = state.difficulty or "medium"
        if last_eval_score >= 8.0:
            adapted_diff = "hard" if cur_diff in ["medium", "hard"] else "medium"
        elif last_eval_score < 5.0:
            adapted_diff = "easy" if cur_diff in ["easy", "medium"] else "medium"
        else:
            adapted_diff = cur_diff
        state.difficulty = adapted_diff

        # Update skill score
        state.skill_scores = ScoringManager.update_skill_score(
            state.skill_scores or {}, state.current_topic, last_eval_score
        )
        state.weak_topics, state.strong_topics = ScoringManager.categorize_topics(state.skill_scores)

        # 5. Determine if a targeted conversational follow-up probe is warranted
        depth_score = float(last_eval_dict.get("depth_score", 7.0)) if last_eval_dict else 7.0
        evidence_list = last_eval_dict.get("evidence", []) if last_eval_dict else []
        turn_count_on_topic = 1 + (state.covered_topics or []).count(state.current_topic)

        should_follow_up, reason_cat = FollowUpEngine.should_follow_up(
            last_eval_score=last_eval_score,
            evidence=evidence_list,
            depth_score=depth_score,
            turn_count_on_topic=turn_count_on_topic,
            time_remaining_seconds=remaining_sec,
            candidate_answer=last_answer_text,
            last_eval_dict=last_eval_dict,
            topic=state.current_topic,
            memory=memory
        )

        next_question: Optional[Question] = None

        if should_follow_up:
            state.interview_stage = "adaptive_probe" if last_eval_score < 7.0 else "deep_dive"

            follow_up_data = await FollowUpEngine.generate_adaptive_follow_up(
                topic=state.current_topic,
                question_text=prev_q_text,
                candidate_answer=last_answer_text or "",
                eval_feedback=last_eval_dict.get("feedback_text", "") if last_eval_dict else "",
                reason_category=reason_cat,
                target_level=interview.target_level,
                eval_dict=last_eval_dict,
                asked_texts=asked_texts,
                memory=memory
            )

            candidate_q_text = follow_up_data.get("question_text", "").strip()

            # Strict duplicate gate for follow-up questions
            is_dup = is_duplicate_question(candidate_q_text, asked_texts) or MemoryManager.is_semantic_duplicate(candidate_q_text, memory)
            if candidate_q_text and not is_dup:
                next_question = Question(
                    company_id=interview.company_id,
                    role_id=interview.role_id,
                    topic=state.current_topic,
                    difficulty=state.difficulty,
                    question_type="technical" if interview.interview_type == "technical" else interview.interview_type,
                    question_text=candidate_q_text,
                    expected_concepts=follow_up_data.get("expected_concepts", [state.current_topic]),
                    follow_ups=follow_up_data.get("follow_ups", [])
                )
                self.db.add(next_question)
                await self.db.commit()
                await self.db.refresh(next_question)
            else:
                should_follow_up = False

        if not should_follow_up:
            # 6. Standard Competency Advance & Gradual Difficulty Adaptation
            state.interview_stage = AdaptiveStateMachine.determine_next_stage(
                state.questions_asked_count,
                remaining_sec,
                total_duration_sec,
                interview_type=interview.interview_type
            )

            # Mark current topic covered
            if state.current_topic and state.current_topic not in (state.covered_topics or []):
                if state.covered_topics is None:
                    state.covered_topics = []
                state.covered_topics.append(state.current_topic)
                if state.remaining_topics and state.current_topic in state.remaining_topics:
                    state.remaining_topics.remove(state.current_topic)

            next_diff, next_topic, skill_scores, weak, strong = AdaptiveStateMachine.adapt_difficulty_and_topic(
                current_difficulty=state.difficulty,
                last_eval_score=last_eval_score,
                current_topic=state.current_topic,
                covered_topics=state.covered_topics or [],
                remaining_topics=state.remaining_topics or [],
                skill_scores=state.skill_scores or {},
                weak_topics=state.weak_topics or [],
                strong_topics=state.strong_topics or []
            )

            state.difficulty = next_diff
            state.current_topic = next_topic
            state.skill_scores = skill_scores
            state.weak_topics = weak
            state.strong_topics = strong

            # Format resume context string for question selector
            resume_context_str = None
            if memory.skills:
                resume_context_str = f"Skills: {', '.join(memory.skills[:8])}"

            # Select or generate next question with full structured memory
            next_question = await self.question_selector.select_or_generate_question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=next_topic,
                difficulty=next_diff,
                asked_question_ids=asked_question_ids,
                interview_type=interview.interview_type,
                resume_context=resume_context_str,
                eval_dict=last_eval_dict,
                memory=memory
            )

        state.current_question_id = next_question.id if next_question else None
        await self.db.commit()
        await self.db.refresh(state)
        return state, next_question, False
