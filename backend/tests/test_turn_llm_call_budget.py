"""A turn spends at most two provider calls: one to score, one to ask.

The third call was reachable through the follow-up path. When the engine decided
to probe deeper it generated a follow-up question, checked it against everything
already asked, and -- if it was a duplicate -- abandoned the follow-up and fell
through to the standard branch, which generated another question from scratch.
That is a second question-generation round trip inside a single turn the
candidate is already waiting through, and it can return a duplicate just as
easily as the first one did.
"""

import uuid
import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.db.models import User, Company, Role, Interview, Question, Answer, Evaluation
from app.interview.engine import AdaptiveInterviewEngine
from app.interview.conversation import FollowUpEngine
from app.interview.question_selector import QuestionSelector


STRONG_EVAL = {
    "correctness_score": 8.5,
    "relevance_score": 8.5,
    "reasoning_score": 8.0,
    "depth_score": 4.0,          # low depth -> the engine wants to probe deeper
    "communication_score": 8.0,
    "overall_question_score": 7.6,
    "evidence": ["candidate described a B-tree index"],
    "feedback_text": "Correct on mechanics, thin on trade-offs.",
    "missing_concepts": ["write amplification"],
    "misconceptions": [],
}


async def _seed_interview(db):
    role = (await db.execute(select(Role).limit(1))).scalars().first()
    assert role is not None, "seed data must provide at least one role"

    user = User(
        email=f"budget_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("SecurePassword123!"),
        full_name="Turn Budget Candidate",
        role="candidate",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    interview = Interview(
        candidate_id=user.id,
        company_id=role.company_id,
        role_id=role.id,
        mode="text",
        interview_type="technical",
        duration_minutes=30,
        target_level="entry",
        status="in_progress",
    )
    db.add(interview)
    await db.commit()
    await db.refresh(interview)

    q = Question(
        company_id=role.company_id,
        role_id=role.id,
        topic="Database Indexing",
        difficulty="medium",
        question_type="technical",
        question_text="How does a database index change the cost of a lookup?",
        expected_concepts=["B-tree", "write cost"],
        follow_ups=[],
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    engine = AdaptiveInterviewEngine(db)
    state = await engine.initialize_interview_state(
        interview, ["Database Indexing", "API Security"], initial_question_id=q.id
    )

    ans = Answer(
        interview_id=interview.id,
        question_id=q.id,
        candidate_answer_text="An index keeps a sorted B-tree so lookups are logarithmic.",
    )
    db.add(ans)
    await db.commit()
    await db.refresh(ans)
    db.add(Evaluation(answer_id=ans.id, **{
        "correctness_score": STRONG_EVAL["correctness_score"],
        "relevance_score": STRONG_EVAL["relevance_score"],
        "reasoning_score": STRONG_EVAL["reasoning_score"],
        "depth_score": STRONG_EVAL["depth_score"],
        "communication_score": STRONG_EVAL["communication_score"],
        "overall_question_score": STRONG_EVAL["overall_question_score"],
        "evidence": STRONG_EVAL["evidence"],
        "feedback_text": STRONG_EVAL["feedback_text"],
        "confidence_score": 0.9,
        "human_review_required": False,
    }))
    await db.commit()
    return engine, interview, state, q, ans


@pytest.mark.asyncio
async def test_duplicate_follow_up_does_not_spend_a_second_generation_call(monkeypatch):
    """A duplicate follow-up must not cost a second question-generation call."""
    async with AsyncSessionLocal() as db:
        engine, interview, state, question, ans = await _seed_interview(db)

        calls = {"follow_up": 0, "generation": 0}

        async def fake_follow_up(**kwargs):
            calls["follow_up"] += 1
            # Word-for-word what was already asked, so the duplicate gate fires.
            return {
                "question_text": question.question_text,
                "expected_concepts": ["B-tree"],
                "follow_ups": [],
            }

        monkeypatch.setattr(FollowUpEngine, "generate_adaptive_follow_up", fake_follow_up)
        monkeypatch.setattr(
            FollowUpEngine, "should_follow_up",
            staticmethod(lambda **kw: (True, "probe_missing_depth")),
        )

        real_select = QuestionSelector.select_or_generate_question

        async def counting_select(self, *args, **kwargs):
            if kwargs.get("allow_llm_generation", True):
                calls["generation"] += 1
            return await real_select(self, *args, **kwargs)

        monkeypatch.setattr(QuestionSelector, "select_or_generate_question", counting_select)

        updated_state, next_question, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=STRONG_EVAL["overall_question_score"],
            asked_question_ids=[question.id],
            last_eval_dict=STRONG_EVAL,
            last_answer_text=ans.candidate_answer_text,
        )

        assert calls["follow_up"] == 1, "the follow-up probe itself should still be attempted"
        assert calls["generation"] == 0, (
            "a duplicate follow-up fell through to a second LLM question generation; "
            "the turn must finish from the local selection path instead"
        )
        assert not is_completed
        assert next_question is not None, "the turn must still produce a question to ask"
        assert next_question.question_text != question.question_text, (
            "the replacement question must not repeat the one already asked"
        )


@pytest.mark.asyncio
async def test_both_follow_ups_duplicate_still_spends_no_second_call(monkeypatch):
    """The backstop: when even the local probe repeats, do not generate again.

    The previous test is rescued by the deterministic probe, which produces a
    fresh question without a provider call. This one removes that rescue too --
    every follow-up route returns something already asked -- so the turn is
    forced down the standard branch. That branch is where the third call lived.
    """
    async with AsyncSessionLocal() as db:
        engine, interview, state, question, ans = await _seed_interview(db)

        calls = {"generation": 0}

        async def fake_follow_up(**kwargs):
            return {"question_text": question.question_text, "expected_concepts": [], "follow_ups": []}

        monkeypatch.setattr(FollowUpEngine, "generate_adaptive_follow_up", fake_follow_up)
        monkeypatch.setattr(
            FollowUpEngine, "should_follow_up",
            staticmethod(lambda **kw: (True, "probe_missing_depth")),
        )
        # The local probe repeats the asked question too, so nothing rescues it.
        monkeypatch.setattr(
            FollowUpEngine, "generate_deterministic_follow_up",
            staticmethod(lambda **kw: {"question_text": question.question_text,
                                       "expected_concepts": [], "follow_ups": []}),
        )

        real_select = QuestionSelector.select_or_generate_question

        async def counting_select(self, *args, **kwargs):
            if kwargs.get("allow_llm_generation", True):
                calls["generation"] += 1
            return await real_select(self, *args, **kwargs)

        monkeypatch.setattr(QuestionSelector, "select_or_generate_question", counting_select)

        _, next_question, is_completed = await engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=STRONG_EVAL["overall_question_score"],
            asked_question_ids=[question.id],
            last_eval_dict=STRONG_EVAL,
            last_answer_text=ans.candidate_answer_text,
        )

        assert calls["generation"] == 0, (
            "the turn fell through to a second LLM question generation after its "
            "follow-up call was already spent"
        )
        assert not is_completed
        assert next_question is not None
        assert next_question.question_text != question.question_text


@pytest.mark.asyncio
async def test_no_generation_path_still_returns_an_unasked_question():
    """allow_llm_generation=False must never return a question already asked."""
    async with AsyncSessionLocal() as db:
        role = (await db.execute(select(Role).limit(1))).scalars().first()
        selector = QuestionSelector(db)

        asked = (await db.execute(
            select(Question).where(Question.question_type == "technical").limit(3)
        )).scalars().all()
        asked_ids = [q.id for q in asked]
        asked_texts = [q.question_text for q in asked]

        picked = await selector.select_or_generate_question(
            company_id=role.company_id,
            role_id=role.id,
            topic="API Security",
            difficulty="medium",
            asked_question_ids=asked_ids,
            interview_type="technical",
            allow_llm_generation=False,
        )

        assert picked is not None
        assert picked.id not in asked_ids
        assert picked.question_text not in asked_texts
