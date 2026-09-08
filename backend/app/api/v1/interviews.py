import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.core.database import get_db, engine as _db_engine
from app.core.security import get_current_user_payload, sanitize_input
from app.db.models import User, Interview, InterviewState, Role, Question, Answer, Evaluation, Company, Resume, ResumeProfile
from app.schemas.interview import (
    InterviewCreate, InterviewOut, CandidateAnswerSubmit,
    AnswerTurnResponse, QuestionOut, AnswerItemOut, InterviewStateOut
)
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.timer import InterviewTimer
from app.evaluation.evaluator import AnswerEvaluator
from app.reports.generator import ReportGenerator

router = APIRouter(prefix="/interviews", tags=["Adaptive Interview Engine"])

# ── Turn serialisation ────────────────────────────────────────────────────────
#
# A turn is four separate commits (answer, evaluation, state, next question).
# The "has this question already been answered?" guard is a SELECT taken before
# the first of them, so two submissions for the same interview that overlap in
# that window both read "no answer yet" and both insert one -- duplicate answers,
# duplicate evaluations, and a questions_asked_count that no longer matches the
# stored answers. Serialising per interview closes that window.
#
# The asyncio lock covers the whole turn within this process. The Postgres row
# lock additionally covers the SELECT-then-INSERT window across workers; it is
# released by the turn's first commit, which is why the in-process lock is kept
# as well rather than replaced.
_TURN_LOCKS: dict[int, asyncio.Lock] = {}
_TURN_LOCKS_GUARD = asyncio.Lock()

# Row-level locking is Postgres/MySQL syntax; SQLite has no FOR UPDATE and
# serialises writers itself, so the in-process lock is the whole guarantee there.
_SUPPORTS_ROW_LOCK = _db_engine.dialect.name in ("postgresql", "mysql")


@asynccontextmanager
async def _interview_turn_lock(interview_id: int):
    async with _TURN_LOCKS_GUARD:
        lock = _TURN_LOCKS.setdefault(interview_id, asyncio.Lock())
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
        async with _TURN_LOCKS_GUARD:
            # Drop the entry only when nobody else holds or awaits it, so the
            # registry cannot grow once for every interview ever run.
            if not lock.locked() and _TURN_LOCKS.get(interview_id) is lock:
                _TURN_LOCKS.pop(interview_id, None)


def _eval_dict_from_row(ev: Evaluation) -> dict:
    """Rebuild the response payload from a stored evaluation, for replays."""
    return {
        "correctness_score": ev.correctness_score,
        "relevance_score": ev.relevance_score,
        "reasoning_score": ev.reasoning_score,
        "depth_score": ev.depth_score,
        "communication_score": ev.communication_score,
        "overall_question_score": ev.overall_question_score,
        "feedback_text": ev.feedback_text,
        "evidence": ev.evidence or [],
        "confidence_score": ev.confidence_score,
        "human_review_required": ev.human_review_required,
    }


def _state_out_from(state) -> InterviewStateOut:
    return InterviewStateOut(
        current_topic=state.current_topic,
        difficulty=state.difficulty,
        time_remaining_seconds=state.time_remaining_seconds,
        questions_asked_count=state.questions_asked_count,
        current_question_id=state.current_question_id,
        skill_scores=state.skill_scores or {},
        weak_topics=state.weak_topics or [],
        strong_topics=state.strong_topics or [],
        covered_topics=state.covered_topics or [],
        remaining_topics=state.remaining_topics or [],
        interview_stage=state.interview_stage
    )


async def _replay_turn(db: AsyncSession, interview: Interview, state, evaluation: Evaluation) -> AnswerTurnResponse:
    """Return the already-computed result of a turn without repeating it.

    Used when a submission targets a question that has already been answered and
    scored: the retry gets the same evaluation and the same pending question it
    would have got had the original response reached it, and nothing new is
    written.
    """
    next_q_out = None
    if interview.status != "completed" and state and state.current_question_id:
        res_q = await db.execute(select(Question).where(Question.id == state.current_question_id))
        nq = res_q.scalars().first()
        if nq:
            next_q_out = QuestionOut(
                id=nq.id, topic=nq.topic, subtopic=nq.subtopic, difficulty=nq.difficulty,
                question_type=nq.question_type, question_text=nq.question_text,
                expected_concepts=nq.expected_concepts or [], follow_ups=nq.follow_ups or []
            )
    return AnswerTurnResponse(
        evaluation=_eval_dict_from_row(evaluation),
        next_question=next_q_out,
        interview_state=_state_out_from(state),
        is_completed=interview.status == "completed",
        closing_message=None,
        termination_reason=state.interview_stage if interview.status == "completed" else None
    )


def format_interview_out(interview: Interview, current_q: Question = None, answers: list = None) -> InterviewOut:
    formatted_answers = []
    if answers:
        for a in answers:
            eval_dict = None
            if hasattr(a, 'evaluation') and a.evaluation:
                eval_dict = {
                    "correctness_score": a.evaluation.correctness_score,
                    "relevance_score": a.evaluation.relevance_score,
                    "reasoning_score": a.evaluation.reasoning_score,
                    "depth_score": a.evaluation.depth_score,
                    "communication_score": a.evaluation.communication_score,
                    "overall_question_score": a.evaluation.overall_question_score,
                    "feedback_text": a.evaluation.feedback_text,
                    "evidence": a.evaluation.evidence or []
                }
            formatted_answers.append(AnswerItemOut(
                id=a.id,
                question_id=a.question_id,
                question_text=a.question.question_text if hasattr(a, 'question') and a.question else "Interview Question",
                candidate_answer_text=a.candidate_answer_text,
                created_at=a.created_at,
                evaluation=eval_dict
            ))

    cur_q_out = None
    if current_q:
        cur_q_out = QuestionOut(
            id=current_q.id,
            topic=current_q.topic,
            subtopic=current_q.subtopic,
            difficulty=current_q.difficulty,
            question_type=current_q.question_type,
            question_text=current_q.question_text,
            expected_concepts=current_q.expected_concepts or [],
            follow_ups=current_q.follow_ups or []
        )

    state_out = None
    if interview.state:
        state_out = InterviewStateOut(
            current_topic=interview.state.current_topic,
            difficulty=interview.state.difficulty,
            time_remaining_seconds=interview.state.time_remaining_seconds,
            questions_asked_count=interview.state.questions_asked_count,
            current_question_id=interview.state.current_question_id,
            skill_scores=interview.state.skill_scores or {},
            weak_topics=interview.state.weak_topics or [],
            strong_topics=interview.state.strong_topics or [],
            covered_topics=interview.state.covered_topics or [],
            remaining_topics=interview.state.remaining_topics or [],
            interview_stage=interview.state.interview_stage
        )

    return InterviewOut(
        id=interview.id,
        candidate_id=interview.candidate_id,
        company_id=interview.company_id,
        role_id=interview.role_id,
        company_name=interview.company.name if getattr(interview, 'company', None) else None,
        role_title=interview.role.title if getattr(interview, 'role', None) else None,
        mode=interview.mode,
        interview_type=getattr(interview, 'interview_type', 'technical') or 'technical',
        duration_minutes=interview.duration_minutes,
        target_level=interview.target_level,
        status=interview.status,
        start_time=interview.start_time,
        end_time=interview.end_time,
        created_at=interview.created_at,
        state=state_out,
        current_question=cur_q_out,
        answers=formatted_answers
    )

@router.post("", response_model=InterviewOut)
async def create_interview(
    interview_in: InterviewCreate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    
    # Verify company and role exist and match
    stmt_role = select(Role).options(selectinload(Role.company)).where(Role.id == interview_in.role_id)
    res_role = await db.execute(stmt_role)
    role = res_role.scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Selected target role not found.")

    if role.company_id != interview_in.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected role does not belong to the specified target company."
        )

    new_interview = Interview(
        candidate_id=user_id,
        company_id=interview_in.company_id,
        role_id=interview_in.role_id,
        mode=interview_in.mode,
        interview_type=interview_in.interview_type or "technical",
        duration_minutes=interview_in.duration_minutes,
        target_level=interview_in.target_level,
        status="in_progress",
        start_time=datetime.utcnow()
    )
    db.add(new_interview)
    await db.commit()
    await db.refresh(new_interview)

    # 1. Fetch Candidate Name & Resume Context for personalized persona framing
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    cand_user = res_user.scalars().first()
    cand_name = cand_user.full_name if cand_user else None

    stmt_resume = (
        select(Resume)
        .options(selectinload(Resume.resume_profile))
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    )
    res_resume = await db.execute(stmt_resume)
    latest_resume = res_resume.scalars().first()
    resume_context = None
    if latest_resume and latest_resume.resume_profile:
        rp = latest_resume.resume_profile
        skills_str = ", ".join(rp.skills[:8]) if rp.skills else "Software engineering background"
        edu_str = rp.education[0].get("degree", "Degree") if (rp.education and len(rp.education) > 0) else "Computer Science"
        resume_context = f"Skills: {skills_str}; Education: {edu_str}"

    # 2. Stage 1 Warm-up Question grounded in company culture and role
    from app.interview.persona import InterviewPersonaBuilder
    warmup_data = await InterviewPersonaBuilder.generate_warmup_question(
        company=role.company,
        role=role,
        candidate_name=cand_name,
        question_index=0,
        resume_context=resume_context
    )

    first_q = Question(
        company_id=new_interview.company_id,
        role_id=new_interview.role_id,
        topic=warmup_data.get("topic", "Introduction & Motivation"),
        difficulty="easy",
        question_type="hr",
        question_text=warmup_data["question_text"],
        expected_concepts=warmup_data.get("expected_concepts", ["Personal introduction", "Role motivation"]),
        follow_ups=warmup_data.get("follow_ups", [])
    )
    db.add(first_q)
    await db.commit()
    await db.refresh(first_q)

    engine = AdaptiveInterviewEngine(db)
    key_topics = role.key_topics or ["Data Structures", "System Design", "Database Indexing", "API Security"]
    state = await engine.initialize_interview_state(new_interview, key_topics, initial_question_id=first_q.id)

    stmt_fetch = select(Interview).options(
        selectinload(Interview.state),
        selectinload(Interview.company),
        selectinload(Interview.role)
    ).where(Interview.id == new_interview.id)
    res_fetch = await db.execute(stmt_fetch)
    interview = res_fetch.scalars().first()

    return format_interview_out(interview, current_q=first_q, answers=[])

@router.get("/history", response_model=list[InterviewOut])
async def get_interview_history(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = select(Interview).options(
        selectinload(Interview.state),
        selectinload(Interview.company),
        selectinload(Interview.role),
        selectinload(Interview.answers).selectinload(Answer.question),
        selectinload(Interview.answers).selectinload(Answer.evaluation)
    ).where(Interview.candidate_id == user_id).order_by(Interview.created_at.desc())
    res = await db.execute(stmt)
    interviews = res.scalars().all()
    return [format_interview_out(i, answers=i.answers) for i in interviews]

@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview_session(
    interview_id: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    user_role = payload.get("role", "candidate")

    stmt = select(Interview).options(
        selectinload(Interview.state),
        selectinload(Interview.company),
        selectinload(Interview.role),
        selectinload(Interview.answers).selectinload(Answer.question),
        selectinload(Interview.answers).selectinload(Answer.evaluation)
    ).where(Interview.id == interview_id)
    res = await db.execute(stmt)
    interview = res.scalars().first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found.")
        
    if interview.candidate_id != user_id and user_role not in ["admin", "placement_staff"]:
        raise HTTPException(status_code=403, detail="Unauthorized to access this interview session.")

    # Recalculate remaining seconds
    if interview.state and interview.status == "in_progress":
        rem = InterviewTimer.calculate_remaining_seconds(interview.start_time, interview.duration_minutes)
        interview.state.time_remaining_seconds = rem
        if rem <= 0:
            interview.status = "completed"
            interview.end_time = datetime.utcnow()
            report_gen = ReportGenerator(db)
            await report_gen.generate_interview_report(interview_id)
        await db.commit()

    # Load active question if in progress
    current_q = None
    if interview.status == "in_progress" and interview.state and interview.state.current_question_id:
        stmt_q = select(Question).where(Question.id == interview.state.current_question_id)
        res_q = await db.execute(stmt_q)
        current_q = res_q.scalars().first()

    if not current_q and interview.status == "in_progress":
        engine = AdaptiveInterviewEngine(db)
        asked_ids = [a.question_id for a in interview.answers]
        current_q = await engine.question_selector.select_or_generate_question(
            company_id=interview.company_id,
            role_id=interview.role_id,
            topic=interview.state.current_topic if interview.state else "General CS",
            difficulty=interview.state.difficulty if interview.state else "medium",
            asked_question_ids=asked_ids,
            interview_type=interview.interview_type
        )
        if interview.state:
            interview.state.current_question_id = current_q.id
            await db.commit()

    return format_interview_out(interview, current_q=current_q, answers=interview.answers)

@router.post("/{interview_id}/answer", response_model=AnswerTurnResponse)
async def submit_answer_turn(
    interview_id: int,
    answer_in: CandidateAnswerSubmit,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    user_role = payload.get("role", "candidate")

    # Validate answer text is non-empty
    if not answer_in.answer_text or not isinstance(answer_in.answer_text, str) or not answer_in.answer_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer cannot be empty."
        )

    stmt = select(Interview).options(
        selectinload(Interview.state),
        selectinload(Interview.company),
        selectinload(Interview.role),
        selectinload(Interview.answers)
    ).where(Interview.id == interview_id)
    res = await db.execute(stmt)
    interview = res.scalars().first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if interview.candidate_id != user_id and user_role not in ["admin", "placement_staff"]:
        raise HTTPException(status_code=403, detail="Unauthorized to submit answer for this interview.")

    if interview.status == "completed":
        st = interview.state
        state_out = InterviewStateOut(
            current_topic=st.current_topic if st else "Completed",
            difficulty=st.difficulty if st else "medium",
            time_remaining_seconds=0,
            questions_asked_count=st.questions_asked_count if st else len(interview.answers),
            current_question_id=None,
            skill_scores=st.skill_scores if st else {},
            weak_topics=st.weak_topics if st else [],
            strong_topics=st.strong_topics if st else [],
            covered_topics=st.covered_topics if st else [],
            remaining_topics=[],
            interview_stage=st.interview_stage if st else "completed"
        )
        return AnswerTurnResponse(
            evaluation={
                "correctness_score": 0.0,
                "relevance_score": 0.0,
                "reasoning_score": 0.0,
                "depth_score": 0.0,
                "communication_score": 0.0,
                "overall_question_score": 0.0,
                "feedback_text": "Interview session is completed.",
                "evidence": [],
                "confidence_score": 1.0,
                "human_review_required": False
            },
            next_question=None,
            interview_state=state_out,
            is_completed=True,
            closing_message="Thank you for completing your interview today. Your evaluation report is now available.",
            termination_reason=st.interview_stage if st else "completed"
        )


    # The question this request was written against, read before it queues for
    # the lock. If the interview has moved past it by the time the lock is held,
    # another submission answered it first and this one is a duplicate.
    entry_q_id = interview.state.current_question_id if interview.state else None

    # Serialise every turn of this interview. Everything below reads state,
    # decides which question is being answered and then writes; overlapping
    # submissions that interleave there duplicate the turn.
    async with _interview_turn_lock(interview_id):
        if _SUPPORTS_ROW_LOCK:
            await db.execute(select(Interview.id).where(Interview.id == interview_id).with_for_update())
        # Re-read after acquiring the lock: a submission that queued behind
        # another one must not act on the state it saw before waiting.
        await db.refresh(interview)
        if interview.state is not None:
            await db.refresh(interview.state)
        res_ans = await db.execute(
            select(Answer)
            .where(Answer.interview_id == interview_id)
            .order_by(Answer.created_at.desc(), Answer.id.desc())
        )
        stored_answers = res_ans.scalars().all()

        engine = AdaptiveInterviewEngine(db)
        state = interview.state
        if not state:
            state = await engine.get_current_state(interview_id)

        submitted_text = answer_in.answer_text.strip()

        # This submission raced another one for the same question and lost: the
        # interview advanced while it was queued. Without this it would be
        # scored against whatever question the winner moved on to -- a question
        # the candidate has not been shown. Clients that send question_id are
        # matched exactly further down and never reach this.
        if (
            answer_in.question_id is None
            and entry_q_id is not None
            and state is not None
            and state.current_question_id != entry_q_id
        ):
            raced = next((a for a in stored_answers if a.question_id == entry_q_id), None)
            if raced is not None:
                res_prev = await db.execute(select(Evaluation).where(Evaluation.answer_id == raced.id))
                prev_eval = res_prev.scalars().first()
                if prev_eval is not None:
                    return await _replay_turn(db, interview, state, prev_eval)

        # 1. Identify which question candidate is answering
        target_q_id = answer_in.question_id or (state.current_question_id if state else None)
        if not target_q_id:
            asked_ids = [a.question_id for a in interview.answers]
            q_obj = await engine.question_selector.select_or_generate_question(
                company_id=interview.company_id,
                role_id=interview.role_id,
                topic=state.current_topic if state else "Technical",
                difficulty=state.difficulty if state else "medium",
                asked_question_ids=asked_ids,
                interview_type=interview.interview_type
            )
            target_q_id = q_obj.id

        stmt_q = select(Question).where(Question.id == target_q_id)
        res_q = await db.execute(stmt_q)
        question = res_q.scalars().first()
        if not question:
            raise HTTPException(status_code=404, detail="Target question for answer evaluation not found.")

        # This question may already carry an answer: a resubmission, or a turn whose
        # answer was committed but whose evaluation and state advance never were
        # (a restart, a dropped connection, a failure inside the engine). The two
        # cases need opposite handling, so they are told apart by the evaluation.
        existing_ans = next((a for a in stored_answers if a.question_id == question.id), None)
        if existing_ans is not None:
            res_ev = await db.execute(select(Evaluation).where(Evaluation.answer_id == existing_ans.id))
            existing_eval = res_ev.scalars().first()
            if existing_eval is not None:
                # Already scored: hand back that turn's result unchanged. Repeating
                # it would store a second evaluation and consume a second question.
                return await _replay_turn(db, interview, state, existing_eval)
            # Scored nowhere: finish the interrupted turn from the answer already
            # on record rather than refusing it, which used to strand the
            # candidate on a question that could never be submitted again.
            ans = existing_ans
        else:
            # 2. Save candidate answer safely before invoking evaluation
            ans = Answer(
                interview_id=interview_id,
                question_id=question.id,
                candidate_answer_text=submitted_text,
                audio_url=answer_in.audio_url,
                stt_latency_ms=answer_in.stt_latency_ms or 0
            )
            db.add(ans)
            await db.commit()
            await db.refresh(ans)

        # The turn is now anchored to a stored answer; score that text, so a
        # resumed turn is evaluated on what the candidate actually submitted.
        answer_text = ans.candidate_answer_text

        # 3. Evaluate Answer with safe fallback to protect persisted answer
        try:
            eval_dict = await AnswerEvaluator.evaluate_answer(
                question_text=question.question_text,
                expected_concepts=question.expected_concepts or [],
                candidate_answer=answer_text,
                topic=question.topic,
                question_type=question.question_type or "technical"
            )
        except Exception:
            # evaluate_answer() already handles LLM/provider failures with its own
            # deterministic fallback; anything reaching here failed before that net
            # was in place. Reuse the same rule-based evaluator rather than storing
            # an unearned passing score.
            try:
                eval_dict = AnswerEvaluator._deterministic_fallback_evaluation(
                    safe_answer=sanitize_input(answer_text),
                    expected_concepts=question.expected_concepts or [],
                    topic=question.topic,
                    question_type=question.question_type or "technical",
                    question_text=question.question_text
                )
            except Exception:
                # Unrecoverable: the answer is already persisted, but no score can
                # be justified, so report the failure instead of inventing one.
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Answer saved, but evaluation is temporarily unavailable. Please retry."
                )

        evaluation = Evaluation(
            answer_id=ans.id,
            correctness_score=eval_dict["correctness_score"],
            relevance_score=eval_dict["relevance_score"],
            reasoning_score=eval_dict["reasoning_score"],
            depth_score=eval_dict["depth_score"],
            communication_score=eval_dict["communication_score"],
            overall_question_score=eval_dict["overall_question_score"],
            evidence=eval_dict["evidence"],
            feedback_text=eval_dict["feedback_text"],
            confidence_score=eval_dict["confidence_score"],
            human_review_required=eval_dict["human_review_required"]
        )
        db.add(evaluation)
        try:
            await db.commit()
        except IntegrityError:
            # evaluations.answer_id is unique: another worker scored this same
            # answer while this turn was in flight (only reachable across
            # processes, where the in-process lock does not apply). Its result
            # stands; replay it rather than raising or scoring twice.
            await db.rollback()
            res_ev = await db.execute(select(Evaluation).where(Evaluation.answer_id == ans.id))
            winner = res_ev.scalars().first()
            if winner is None:
                raise
            await db.refresh(interview)
            return await _replay_turn(db, interview, state, winner)

        # 4. Adaptive State Machine Progression
        # A resumed turn already has its answer on record, so dedupe: the
        # engine takes this as the set of questions not to ask again.
        asked_ids = list(dict.fromkeys([a.question_id for a in interview.answers] + [question.id]))
        updated_state, next_question, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=eval_dict["overall_question_score"],
            asked_question_ids=asked_ids,
            last_eval_dict=eval_dict,
            last_answer_text=answer_text
        )

        # If interview finished, trigger automatic report generation and construct polite closing
        closing_msg = None
        term_reason = None
        if is_completed:
            report_gen = ReportGenerator(db)
            await report_gen.generate_interview_report(interview_id)
            term_reason = updated_state.interview_stage or "completed"
            if updated_state.interview_stage == "early_conclusion":
                cand_name = None
                stmt_u = select(User).where(User.id == user_id)
                res_u = await db.execute(stmt_u)
                u_obj = res_u.scalars().first()
                if u_obj:
                    cand_name = u_obj.full_name
                comp_obj = getattr(interview, "company", None)
                if not comp_obj and interview.company_id:
                    stmt_c = select(Company).where(Company.id == interview.company_id)
                    res_c = await db.execute(stmt_c)
                    comp_obj = res_c.scalars().first()
                from app.interview.persona import InterviewPersonaBuilder
                closing_msg = InterviewPersonaBuilder.get_early_conclusion_statement(
                    company=comp_obj,
                    candidate_name=cand_name
                )
            else:
                closing_msg = "Thank you for completing your interview today. We appreciate your time and participation. Your comprehensive evaluation report is now available."

        next_q_out = None
        if next_question:
            next_q_out = QuestionOut(
                id=next_question.id,
                topic=next_question.topic,
                subtopic=next_question.subtopic,
                difficulty=next_question.difficulty,
                question_type=next_question.question_type,
                question_text=next_question.question_text,
                expected_concepts=next_question.expected_concepts or [],
                follow_ups=next_question.follow_ups or []
            )

        state_out = InterviewStateOut(
            current_topic=updated_state.current_topic,
            difficulty=updated_state.difficulty,
            time_remaining_seconds=updated_state.time_remaining_seconds,
            questions_asked_count=updated_state.questions_asked_count,
            current_question_id=updated_state.current_question_id,
            skill_scores=updated_state.skill_scores or {},
            weak_topics=updated_state.weak_topics or [],
            strong_topics=updated_state.strong_topics or [],
            covered_topics=updated_state.covered_topics or [],
            remaining_topics=updated_state.remaining_topics or [],
            interview_stage=updated_state.interview_stage
        )

        return AnswerTurnResponse(
            evaluation=eval_dict,
            interviewer_ack=eval_dict.get("interviewer_ack") or None,
            next_question=next_q_out,
            interview_state=state_out,
            is_completed=is_completed,
            closing_message=closing_msg,
            termination_reason=term_reason
        )


@router.post("/{interview_id}/finish")
async def finish_interview_session(
    interview_id: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db)
):
    user_id = payload["user_id"]
    stmt = select(Interview).where(Interview.id == interview_id, Interview.candidate_id == user_id)
    res = await db.execute(stmt)
    interview = res.scalars().first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    interview.status = "completed"
    interview.end_time = datetime.utcnow()
    await db.commit()

    # Generate final report
    report_gen = ReportGenerator(db)
    report = await report_gen.generate_interview_report(interview_id)
    return {"message": "Interview session completed successfully.", "report_id": report.id}

