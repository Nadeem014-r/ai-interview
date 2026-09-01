import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models import User, Company, Role, Interview, InterviewState, Question, Answer, Evaluation
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.persona import InterviewPersonaBuilder
from app.interview.conversation import FollowUpEngine
from app.interview.memory import InterviewMemory, MemoryManager
from app.voice.tts import TextToSpeechService
from app.ai.mock_provider import MockTTSProvider
from app.reports.generator import ReportGenerator


@pytest.mark.asyncio
async def test_mock_tts_produces_audible_valid_wav():
    """Verify MockTTSProvider produces valid, audible PCM WAV audio with proper headers and audio frames."""
    provider = MockTTSProvider()
    audio_bytes = await provider.synthesize_speech("Tell me about your background in software engineering.")
    
    assert audio_bytes is not None
    assert len(audio_bytes) > 100
    assert audio_bytes.startswith(b"RIFF")
    assert b"WAVEfmt " in audio_bytes
    assert b"data" in audio_bytes
    
    # Check data size is non-zero
    data_idx = audio_bytes.find(b"data")
    assert data_idx != -1
    data_size = int.from_bytes(audio_bytes[data_idx+4:data_idx+8], byteorder="little")
    assert data_size > 0


@pytest.mark.asyncio
async def test_tts_service_returns_valid_metadata_and_bytes():
    """Verify TextToSpeechService returns valid audio bytes and telemetry metadata."""
    audio_bytes, meta = await TextToSpeechService.synthesize_with_metadata(
        text="Explain how database indexes work."
    )
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert meta["success"] is True
    assert meta["size_bytes"] == len(audio_bytes)
    assert meta["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_single_mistake_does_not_terminate_interview():
    """Verify that a single incorrect/weak answer does NOT prematurely terminate the interview."""
    async with AsyncSessionLocal() as db_session:
        company = Company(name=f"TechCorp Test A {datetime.utcnow().timestamp()}", slug=f"techcorp-test-a-{datetime.utcnow().timestamp()}", culture_keywords=["Excellence"])
        db_session.add(company)
        await db_session.commit()
        await db_session.refresh(company)

        role = Role(company_id=company.id, title="Backend Engineer", level="Entry", key_topics=["APIs", "Databases", "Concurrency"])
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)

        user = User(email=f"cand_test1_{datetime.utcnow().timestamp()}@example.com", hashed_password="pw", full_name="Alice Candidate", role="candidate")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="voice",
            interview_type="technical",
            duration_minutes=20,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        db_session.add(interview)
        await db_session.commit()
        await db_session.refresh(interview)

        engine = AdaptiveInterviewEngine(db_session)
        state = await engine.initialize_interview_state(interview, key_topics=["APIs", "Databases", "Concurrency"])

        # Turn 1: Warmup/Intro (good score)
        q1 = Question(company_id=company.id, role_id=role.id, topic="Introduction", difficulty="easy", question_text="Tell me about yourself.")
        db_session.add(q1)
        await db_session.commit()
        state.current_question_id = q1.id

        ans1 = Answer(interview_id=interview.id, question_id=q1.id, candidate_answer_text="I am a CS student interested in backend development.")
        db_session.add(ans1)
        await db_session.commit()

        state, next_q1, is_comp1 = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=7.5,
            asked_question_ids=[q1.id],
            last_eval_dict={"overall_question_score": 7.5, "depth_score": 7.0},
            last_answer_text=ans1.candidate_answer_text
        )
        assert not is_comp1
        assert next_q1 is not None

        # Turn 2: Single weak/incorrect answer on first technical question
        ans2 = Answer(interview_id=interview.id, question_id=next_q1.id, candidate_answer_text="I don't know much about database normalization.")
        db_session.add(ans2)
        await db_session.commit()

        state, next_q2, is_comp2 = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=2.0,
            asked_question_ids=[q1.id, next_q1.id],
            last_eval_dict={"overall_question_score": 2.0, "depth_score": 2.0, "missing_concepts": ["Normalization"]},
            last_answer_text=ans2.candidate_answer_text
        )

        # Must NOT terminate after just 1 mistake!
        assert not is_comp2
        assert interview.status == "in_progress"
        assert next_q2 is not None
        assert state.difficulty == "easy"


@pytest.mark.asyncio
async def test_repeated_failures_trigger_recovery_opportunity():
    """Verify that repeated foundational failures trigger a supportive recovery opportunity question."""
    async with AsyncSessionLocal() as db_session:
        company = Company(name=f"Struggling Test Co {datetime.utcnow().timestamp()}", slug=f"struggling-test-co-{datetime.utcnow().timestamp()}")
        db_session.add(company)
        await db_session.commit()

        role = Role(company_id=company.id, title="Software Engineer", level="Entry", key_topics=["Data Structures", "Algorithms"])
        db_session.add(role)
        await db_session.commit()

        user = User(email=f"cand_struggle_{datetime.utcnow().timestamp()}@example.com", hashed_password="pw", full_name="Bob Stumbler", role="candidate")
        db_session.add(user)
        await db_session.commit()

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="video",
            interview_type="technical",
            duration_minutes=15,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        db_session.add(interview)
        await db_session.commit()

        engine = AdaptiveInterviewEngine(db_session)
        state = await engine.initialize_interview_state(interview, key_topics=["Data Structures", "Algorithms"])

        # Turn 1: Weak intro
        q1 = Question(company_id=company.id, role_id=role.id, topic="Intro", difficulty="easy", question_text="Tell me about yourself.")
        db_session.add(q1)
        await db_session.commit()
        state.current_question_id = q1.id

        ans1 = Answer(interview_id=interview.id, question_id=q1.id, candidate_answer_text="Um, hi, I am Bob.")
        db_session.add(ans1)
        await db_session.commit()

        state, next_q1, _ = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=3.5,
            asked_question_ids=[q1.id],
            last_eval_dict={"overall_question_score": 3.5, "depth_score": 3.0},
            last_answer_text=ans1.candidate_answer_text
        )

        # Turn 2: Technical question -> candidate cannot answer ("I don't know")
        ans2 = Answer(interview_id=interview.id, question_id=next_q1.id, candidate_answer_text="I don't know what a binary tree is.")
        db_session.add(ans2)
        await db_session.commit()

        state, recovery_q, is_comp2 = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=1.5,
            asked_question_ids=[q1.id, next_q1.id],
            last_eval_dict={"overall_question_score": 1.5, "depth_score": 1.0},
            last_answer_text=ans2.candidate_answer_text
        )

        # Should trigger recovery stage
        assert not is_comp2
        assert state.interview_stage == "recovery"
        assert recovery_q is not None
        assert "tell me about a technology, project, or concept" in recovery_q.question_text.lower() or "personally worked with" in recovery_q.question_text.lower()


@pytest.mark.asyncio
async def test_meaningful_recovery_allows_interview_to_continue():
    """Verify that when a candidate provides a meaningful answer to the recovery question, the interview continues."""
    async with AsyncSessionLocal() as db_session:
        company = Company(name=f"Recovery Co {datetime.utcnow().timestamp()}", slug=f"recovery-co-{datetime.utcnow().timestamp()}")
        db_session.add(company)
        await db_session.commit()

        role = Role(company_id=company.id, title="Frontend Engineer", level="Entry", key_topics=["JavaScript", "React"])
        db_session.add(role)
        await db_session.commit()

        user = User(email=f"cand_recovery_{datetime.utcnow().timestamp()}@example.com", hashed_password="pw", full_name="Charlie Resume", role="candidate")
        db_session.add(user)
        await db_session.commit()

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            interview_type="technical",
            duration_minutes=20,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        db_session.add(interview)
        await db_session.commit()

        engine = AdaptiveInterviewEngine(db_session)
        state = await engine.initialize_interview_state(interview, key_topics=["JavaScript", "React"])

        # Put state in recovery stage
        recovery_q = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Practical Skills",
            difficulty="easy",
            question_text="Can you tell me about a project or technology you have personally worked with?"
        )
        db_session.add(recovery_q)
        await db_session.commit()
        state.interview_stage = "recovery"
        state.current_question_id = recovery_q.id

        # Candidate provides meaningful response detailing their project
        recovery_ans = Answer(
            interview_id=interview.id,
            question_id=recovery_q.id,
            candidate_answer_text="I built a responsive task management web app using React and Tailwind CSS. I implemented state management using React hooks and connected to a Node.js REST API."
        )
        db_session.add(recovery_ans)
        await db_session.commit()

        state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=6.8,
            asked_question_ids=[recovery_q.id],
            last_eval_dict={
                "overall_question_score": 6.8,
                "depth_score": 6.5,
                "demonstrated_concepts": ["React", "State Management", "REST API"]
            },
            last_answer_text=recovery_ans.candidate_answer_text
        )

        # Interview must continue and NOT terminate!
        assert not is_completed
        assert interview.status == "in_progress"
        assert state.interview_stage in ["warmup", "core", "adaptive_probe"]
        assert state.difficulty == "easy"
        assert next_q is not None


@pytest.mark.asyncio
async def test_failed_recovery_concludes_interview_professionally():
    """Verify that when recovery fails, interview concludes politely with valid report generation."""
    async with AsyncSessionLocal() as db_session:
        company = Company(name=f"EarlyExit Co {datetime.utcnow().timestamp()}", slug=f"earlyexit-co-{datetime.utcnow().timestamp()}")
        db_session.add(company)
        await db_session.commit()

        role = Role(company_id=company.id, title="ML Engineer", level="Entry", key_topics=["Python", "Machine Learning"])
        db_session.add(role)
        await db_session.commit()

        user = User(email=f"cand_exit_{datetime.utcnow().timestamp()}@example.com", hashed_password="pw", full_name="Dave Nonresponsive", role="candidate")
        db_session.add(user)
        await db_session.commit()

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="voice",
            interview_type="technical",
            duration_minutes=20,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        db_session.add(interview)
        await db_session.commit()

        engine = AdaptiveInterviewEngine(db_session)
        state = await engine.initialize_interview_state(interview, key_topics=["Python", "Machine Learning"])

        recovery_q = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Practical Skills",
            difficulty="easy",
            question_text="Can you tell me about a project or technology you have personally worked with?"
        )
        db_session.add(recovery_q)
        await db_session.commit()
        state.interview_stage = "recovery"
        state.current_question_id = recovery_q.id

        # Candidate fails even the recovery question ("I don't know anything")
        recovery_ans = Answer(
            interview_id=interview.id,
            question_id=recovery_q.id,
            candidate_answer_text="I don't know, I haven't done any projects."
        )
        db_session.add(recovery_ans)
        await db_session.commit()

        state, next_q, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=1.0,
            asked_question_ids=[recovery_q.id],
            last_eval_dict={"overall_question_score": 1.0, "depth_score": 1.0},
            last_answer_text=recovery_ans.candidate_answer_text
        )

        # Must conclude interview professionally
        assert is_completed is True
        assert interview.status == "completed"
        assert state.interview_stage == "early_conclusion"
        assert next_q is None

        # Verify professional exit statement
        exit_msg = InterviewPersonaBuilder.get_early_conclusion_statement(company=company, candidate_name=user.full_name)
        assert "thank you for your time" in exit_msg.lower()
        assert "conclude the interview here" in exit_msg.lower()
        assert "you know nothing" not in exit_msg.lower()
        assert "you failed" not in exit_msg.lower()

        # Verify report generates correctly
        report_gen = ReportGenerator(db_session)
        report = await report_gen.generate_interview_report(interview.id)
        assert report is not None
        assert report.interview_id == interview.id


@pytest.mark.asyncio
async def test_strong_candidate_never_prematurely_terminated():
    """Verify that a strong candidate is never terminated early and escalates in difficulty and depth."""
    async with AsyncSessionLocal() as db_session:
        company = Company(name=f"Google Test Co {datetime.utcnow().timestamp()}", slug=f"google-test-co-{datetime.utcnow().timestamp()}")
        db_session.add(company)
        await db_session.commit()

        role = Role(company_id=company.id, title="Senior Backend Engineer", level="Senior", key_topics=["Distributed Systems", "Concurrency", "Database Scaling"])
        db_session.add(role)
        await db_session.commit()

        user = User(email=f"strong_cand_{datetime.utcnow().timestamp()}@example.com", hashed_password="pw", full_name="Dr. Star Candidate", role="candidate")
        db_session.add(user)
        await db_session.commit()

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="video",
            interview_type="technical",
            duration_minutes=30,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        db_session.add(interview)
        await db_session.commit()

        engine = AdaptiveInterviewEngine(db_session)
        state = await engine.initialize_interview_state(interview, key_topics=["Distributed Systems", "Concurrency", "Database Scaling"])

        # Ask 4 consecutive high-scoring turns
        turns_data = [
            ("I led the distributed cache layer using Redis and raft consensus to guarantee linearizability.", 9.2),
            ("We handled lock contention with distributed leasing and optimistic concurrency control.", 8.9),
            ("To mitigate cache stampede, we used probabilistic early expiration with background refresh.", 9.4),
            ("We partitioned the database using consistent hashing with virtual nodes to avoid hot spots.", 9.1),
        ]

        asked_ids = []
        for i, (ans_text, score) in enumerate(turns_data):
            q = Question(
                company_id=company.id,
                role_id=role.id,
                topic=state.current_topic,
                difficulty=state.difficulty,
                question_text=f"Technical architectural question #{i+1}"
            )
            db_session.add(q)
            await db_session.commit()
            state.current_question_id = q.id
            asked_ids.append(q.id)

            ans = Answer(interview_id=interview.id, question_id=q.id, candidate_answer_text=ans_text)
            db_session.add(ans)
            await db_session.commit()

            state, next_q, is_completed = await engine.process_answer_turn(
                interview=interview,
                state=state,
                last_eval_score=score,
                asked_question_ids=asked_ids,
                last_eval_dict={
                    "overall_question_score": score,
                    "depth_score": 9.0,
                    "evidence": [ans_text[:40]],
                    "demonstrated_concepts": ["Distributed Systems", "Caching", "Concurrency"]
                },
                last_answer_text=ans_text
            )

            assert not is_completed
            assert interview.status == "in_progress"
            assert state.difficulty == "hard"
            assert state.interview_stage in ["deep_dive", "core", "adaptive_probe", "resume_discussion", "behavioral"]
