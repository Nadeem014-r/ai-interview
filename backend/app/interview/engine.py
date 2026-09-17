"""Phase 7/9: Adaptive Interview Engine Orchestrator with Structured Memory.

Coordinates interview lifecycle, planning, evaluation ingestion, skill evolution,
follow-up intelligence, claim tracking, difficulty adaptation, and time-aware stop conditions.
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Company, Interview, InterviewState, Question, Answer, Role, Resume
from app.interview.timer import InterviewTimer
from app.interview.state_machine import AdaptiveStateMachine
from app.interview.question_selector import QuestionSelector, is_duplicate_question
from app.interview.planner import InterviewPlanner
from app.interview.conversation import FollowUpEngine
from app.interview.scoring import ScoringManager
from app.interview.memory import InterviewMemory, MemoryManager

logger = logging.getLogger("ai_interviewer.engine")


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

        # build_interview_memory() replays every persisted answer, and the API
        # persists this turn's answer before calling in -- so ingesting again
        # unconditionally recorded the same turn twice. Every downstream count
        # then double-weighted the newest answer: a single weak reply looked
        # like two consecutive failures and pushed the interview into recovery,
        # and from there into an early conclusion, far sooner than intended.
        last_turn = memory.conversation_turns[-1] if memory.conversation_turns else None
        already_ingested = bool(
            last_turn
            and (last_turn.candidate_answer or "").strip() == (last_answer_text or "").strip()
            and (last_turn.question_text or "") == prev_q_text
        )
        if last_answer_text and not already_ingested:
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

        # 4. Ingest Turn and Analyze Candidate Viability / Knowledge Floor
        # Check if candidate is currently answering a recovery question
        was_recovery_turn = (state.interview_stage == "recovery")
        
        # Determine if current answer is non-responsive or severely struggling
        ans_lower = (last_answer_text or "").lower().strip()
        is_idontknow_or_empty = bool(
            not ans_lower
            or ans_lower in ["i don't know", "i dont know", "no idea", "pass", "skip", "no clue"]
            or (ans_lower.startswith("i don't know") and len(ans_lower) < 25)
            or (ans_lower.startswith("i dont know") and len(ans_lower) < 25)
        )
        is_severely_struggling = (last_eval_score < 4.0 or is_idontknow_or_empty)

        # Handle Recovery Turn Outcome
        if was_recovery_turn:
            # Candidate was given a recovery opportunity to explain something they know.
            # The evaluation score and the answer's content must agree. The text checks
            # corroborate an acceptable score; they never override a failing one. An
            # articulate refusal clears any character or word-count threshold while
            # disclaiming all knowledge, so length is not by itself evidence of recovery.
            has_meaningful_recovery = (
                last_eval_score >= 4.0
                and not is_idontknow_or_empty
                and len(ans_lower) >= 15
                and bool(re.findall(r'\b[a-zA-Z]{3,}\b', ans_lower))
            )

            if has_meaningful_recovery:
                # Recovery SUCCEEDED! Candidate demonstrated baseline familiarity with their chosen subject.
                # Continue interview at an accessible foundational difficulty.
                state.difficulty = "easy"
                state.interview_stage = "core"
            else:
                # Recovery FAILED! Candidate was unable to demonstrate familiarity even with a topic of their own choosing.
                # Conclude the interview early and politely without wasting candidate's time.
                state.interview_stage = "early_conclusion"
                state.current_question_id = None
                interview.status = "completed"
                interview.end_time = datetime.utcnow()
                await self.db.commit()
                return state, None, True

        # Check Consecutive Foundational Failure Threshold (Knowledge Floor)
        # Inspect recent turns to avoid terminating on a single mistake
        # Only turns with a persisted Evaluation carry a performance signal.
        # Unscored turns are excluded so a missing evaluation neither triggers
        # nor suppresses recovery.
        recent_turns = [t for t in memory.conversation_turns if t.score is not None][-3:]
        consecutive_struggling = 0
        for t in reversed(recent_turns):
            t_ans_lower = (t.candidate_answer or "").lower().strip()
            t_is_idk = bool(
                not t_ans_lower
                or t_ans_lower in ["i don't know", "i dont know", "no idea", "pass", "skip", "no clue"]
                or (t_ans_lower.startswith("i don't know") and len(t_ans_lower) < 25)
                or (t_ans_lower.startswith("i dont know") and len(t_ans_lower) < 25)
            )
            if t.score < 4.0 or t_is_idk:
                consecutive_struggling += 1
            else:
                break

        # Trigger Recovery Question if candidate has 2 or more consecutive foundational failures
        # (and is not already in recovery or wrapup)
        should_offer_recovery = (
            not was_recovery_turn
            and state.interview_stage not in ["recovery", "early_conclusion", "wrapup"]
            and state.questions_asked_count >= 2
            and (consecutive_struggling >= 2 or (len(recent_turns) >= 2 and sum(t.score for t in recent_turns[-2:]) / 2.0 < 3.2))
        )

        if should_offer_recovery:
            state.interview_stage = "recovery"
            state.difficulty = "easy"
            
            # Generate supportive recovery question
            company = None
            role = None
            if hasattr(self.db, "get") and callable(self.db.get):
                if interview.company_id:
                    try:
                        company = await self.db.get(Company, interview.company_id)
                    except Exception:
                        company = None
                if interview.role_id:
                    try:
                        role = await self.db.get(Role, interview.role_id)
                    except Exception:
                        role = None

            from app.interview.persona import InterviewPersonaBuilder
            recovery_q_data = await InterviewPersonaBuilder.generate_recovery_question(
                company=company,
                role=role
            )
            
            recovery_q = Question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=recovery_q_data.get("topic", "Practical Project & Skills Overview"),
                difficulty="easy",
                question_type="technical",
                question_text=recovery_q_data.get("question_text", "I see. That's completely okay. Let's take a step back. Can you tell me about a technology, project, or concept that you have personally worked with and feel most comfortable explaining?"),
                expected_concepts=recovery_q_data.get("expected_concepts", ["Demonstrated personal project", "Core technology familiarity"]),
                follow_ups=recovery_q_data.get("follow_ups", ["What was your specific role and what technical challenges did you solve?"])
            )
            self.db.add(recovery_q)
            await self.db.commit()
            await self.db.refresh(recovery_q)
            
            state.current_question_id = recovery_q.id
            await self.db.commit()
            await self.db.refresh(state)
            return state, recovery_q, False

        # 5. Adaptive Difficulty Progression for continuing interview
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
        # covered_topics records each topic at most once, and only when the
        # engine advances off it -- so counting it never exceeded 1 and the
        # "at most two follow-ups per topic" budget in should_follow_up() could
        # never fire. The interview drilled a single topic indefinitely while
        # the remaining competencies went unasked. The turns already spent on
        # this topic are what the budget is about, so count those.
        turn_count_on_topic = max(
            1,
            sum(1 for t in memory.conversation_turns if t.topic == state.current_topic)
        )

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
        # Whether this turn has already spent its provider call on a question.
        # A turn is allowed one: the evaluation, then one question. When the
        # follow-up below is generated and then rejected as a duplicate, the
        # standard path used to generate again -- a third provider round trip
        # for a turn the candidate is already waiting through, and one that can
        # return a duplicate just as easily. The local selection path is used
        # instead, and it cannot repeat an asked question.
        question_llm_call_spent = False

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
            question_llm_call_spent = True

            candidate_q_text = follow_up_data.get("question_text", "").strip()

            # Strict duplicate gate for follow-up questions
            is_dup = is_duplicate_question(candidate_q_text, asked_texts) or MemoryManager.is_semantic_duplicate(candidate_q_text, memory)

            if candidate_q_text and is_dup:
                # The generated probe repeats something already asked. Before
                # abandoning the follow-up, try the deterministic probe for this
                # same topic and reason: it is local, it is grounded in the
                # answer that triggered the follow-up, and it keeps the turn on
                # the thread the interviewer was pulling.
                det = FollowUpEngine.generate_deterministic_follow_up(
                    topic=state.current_topic,
                    reason_category=reason_cat,
                    candidate_answer=last_answer_text or "",
                    target_level=interview.target_level,
                    eval_dict=last_eval_dict,
                    asked_texts=asked_texts,
                    memory=memory
                )
                det_text = (det.get("question_text") or "").strip()
                if det_text and not (
                    is_duplicate_question(det_text, asked_texts)
                    or MemoryManager.is_semantic_duplicate(det_text, memory)
                ):
                    follow_up_data = det
                    candidate_q_text = det_text
                    is_dup = False

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

            # Mark current topic covered. covered_topics/remaining_topics are
            # plain JSON columns with no MutableList tracking, so an in-place
            # append/remove is invisible to the session and is discarded on
            # commit. Reassigning the attribute marks it dirty and persists.
            if state.current_topic and state.current_topic not in (state.covered_topics or []):
                state.covered_topics = (state.covered_topics or []) + [state.current_topic]
                if state.remaining_topics and state.current_topic in state.remaining_topics:
                    remaining = list(state.remaining_topics)
                    remaining.remove(state.current_topic)
                    state.remaining_topics = remaining

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

            # Offer the coding exercise here, at the point where a fresh
            # competency question would otherwise be chosen -- so it takes the
            # place of one normal turn rather than being bolted onto the flow.
            # Follow-up probes, recovery and early conclusion all return before
            # this line, so none of them can be interrupted by it.
            next_question = await self._maybe_build_coding_question(
                interview=interview,
                state=state,
                memory=memory,
                remaining_sec=remaining_sec,
                asked_question_ids=asked_question_ids,
            )
            if next_question is not None:
                state.current_question_id = next_question.id
                await self.db.commit()
                await self.db.refresh(state)
                return state, next_question, False

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
                memory=memory,
                allow_llm_generation=not question_llm_call_spent
            )

        state.current_question_id = next_question.id if next_question else None
        await self.db.commit()
        await self.db.refresh(state)
        return state, next_question, False

    async def _maybe_build_coding_question(
        self,
        interview: "Interview",
        state: "InterviewState",
        memory,
        remaining_sec: int,
        asked_question_ids: List[int],
    ) -> Optional[Question]:
        """Create the interview's one coding exercise, or return None.

        Returns None for every interview that is not a fit, which is most of
        them. Costs no provider call: eligibility is decided from the role, the
        candidate's own skills and the state already in hand.
        """
        try:
            from app.interview.coding_selector import build_coding_question, is_coding_eligible

            stmt_asked = select(Question.question_type).where(Question.id.in_(asked_question_ids or [-1]))
            res_asked = await self.db.execute(stmt_asked)
            already_asked = any((row[0] or "") == "coding" for row in res_asked.all())

            role = None
            company = None
            if interview.role_id:
                try:
                    role = await self.db.get(Role, interview.role_id)
                except Exception:
                    role = None
            if interview.company_id:
                try:
                    company = await self.db.get(Company, interview.company_id)
                except Exception:
                    company = None

            eligible, reason = is_coding_eligible(
                interview_type=interview.interview_type,
                role_title=getattr(role, "title", None),
                required_skills=getattr(role, "required_skills", None),
                role_key_topics=getattr(role, "key_topics", None),
                candidate_skills=getattr(memory, "skills", None),
                questions_asked_count=state.questions_asked_count,
                time_remaining_seconds=remaining_sec,
                interview_stage=state.interview_stage,
                already_asked=already_asked,
            )
            if not eligible:
                logger.debug(f"Coding stage not offered: {reason}")
                return None

            data = build_coding_question(
                topic=state.current_topic or "Problem Solving",
                difficulty=state.difficulty or "medium",
                company_name=getattr(company, "name", None),
                role_title=getattr(role, "title", None),
                candidate_skills=getattr(memory, "skills", None),
            )

            coding_q = Question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=data["topic"],
                subtopic=data["subtopic"],
                difficulty=data["difficulty"],
                question_type="coding",
                question_text=data["question_text"],
                expected_concepts=data["expected_concepts"],
                follow_ups=data["follow_ups"],
            )
            self.db.add(coding_q)
            await self.db.commit()
            await self.db.refresh(coding_q)
            state.interview_stage = "coding"
            return coding_q
        except Exception as e:
            # A coding exercise is an enhancement. If anything about it fails the
            # interview continues with a normal question rather than stopping.
            logger.warning(f"Coding question selection skipped: {e}")
            return None

    # -------------------------------------------------------------------------
    # process_answer_turn_v2: Depth State Machine + Persona Controller overlay
    # Opt-in via ENABLE_DEPTH_STATE_MACHINE=true env flag.
    # Calls the original process_answer_turn() first, then enriches state
    # with DepthStateMachine + QuestionDirective metadata.
    # -------------------------------------------------------------------------

    async def process_answer_turn_v2(
        self,
        interview: "Interview",
        state: "InterviewState",
        last_eval_score: float,
        asked_question_ids: List[int],
        last_eval_dict: Optional[Dict[str, Any]] = None,
        last_answer_text: Optional[str] = None,
        depth_snapshot_dict: Optional[Dict[str, Any]] = None,
    ) -> Tuple["InterviewState", Optional["Question"], bool, Dict[str, Any]]:
        """
        Enhanced answer processing turn with DepthStateMachine overlay.

        Returns the same (state, next_question, is_completed) as process_answer_turn,
        plus a 4th element: depth_metadata dict for the calling layer to use.

        depth_metadata = {
            "current_depth": int (1-5),
            "time_phase": str,
            "depth_label": str,
            "probe_type": str,
            "directive": QuestionDirective,
            "depth_snapshot": dict,  # for DB persistence
            "system_prompt": str,     # persona-enriched system prompt for next turn
        }

        Falls back gracefully to the original process_answer_turn() if the
        depth state machine modules fail to import (e.g., during testing).
        """
        # ── Run the original turn logic first (completely unchanged) ─────────
        state, next_question, is_completed = await self.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=last_eval_score,
            asked_question_ids=asked_question_ids,
            last_eval_dict=last_eval_dict,
            last_answer_text=last_answer_text,
        )

        # ── Depth State Machine overlay ───────────────────────────────────────
        depth_metadata: Dict[str, Any] = {}
        try:
            from app.interview.depth_state_machine import DepthStateMachine, DepthStateSnapshot
            from app.interview.persona_controller import InterviewerPersonaController

            # Restore or initialize DepthStateMachine from snapshot
            if depth_snapshot_dict:
                snap = DepthStateSnapshot.from_dict(depth_snapshot_dict)
            else:
                snap = DepthStateSnapshot()
            dsm = DepthStateMachine(snapshot=snap)

            # Update time phase
            elapsed = (
                (interview.duration_minutes * 60)
                - max(0, state.time_remaining_seconds or 0)
            )
            total = max(1, interview.duration_minutes) * 60
            dsm.update_time_phase(elapsed_seconds=elapsed, total_duration_seconds=total)

            # Update depth from evaluation score
            dsm.update_depth(answer_score=last_eval_score)

            # Get question directive
            directive = dsm.get_directive(
                topic=state.current_topic or "Technical",
                last_answer_text=last_answer_text,
                last_eval_dict=last_eval_dict,
            )

            # Build persona-enriched system prompt for the next question turn
            role_title = "Software Engineer"
            company_name = "the company"
            candidate_name = "the candidate"
            try:
                from sqlalchemy import select
                from app.db.models import Role, Company
                if interview.role_id:
                    res_role = await self.db.execute(
                        select(Role).where(Role.id == interview.role_id)
                    )
                    role_obj = res_role.scalars().first()
                    if role_obj:
                        role_title = role_obj.title or role_title
                if interview.company_id:
                    res_co = await self.db.execute(
                        select(Company).where(Company.id == interview.company_id)
                    )
                    co_obj = res_co.scalars().first()
                    if co_obj:
                        company_name = co_obj.name or company_name
            except Exception:
                pass

            system_prompt = InterviewerPersonaController.build_system_prompt(
                role_title=role_title,
                company_name=company_name,
                candidate_name=candidate_name,
                directive=directive,
                interview_type=interview.interview_type or "technical",
            )

            depth_metadata = {
                "current_depth": dsm.current_depth,
                "time_phase": dsm.current_phase.value,
                "depth_label": directive.depth_label,
                "probe_type": directive.probe_type,
                "directive": directive,
                "depth_snapshot": dsm.get_snapshot().to_dict(),
                "system_prompt": system_prompt,
                "average_score": dsm.average_score,
            }

        except Exception as exc:
            logging.getLogger("ai_interviewer.engine").warning(
                f"DepthStateMachine overlay failed (non-fatal): {exc}"
            )
            depth_metadata = {
                "current_depth": 1,
                "time_phase": "core",
                "depth_label": "Practical",
                "probe_type": "practical_implementation",
                "directive": None,
                "depth_snapshot": {},
                "system_prompt": "",
                "average_score": last_eval_score,
            }

        return state, next_question, is_completed, depth_metadata
