"""Regression cover for Batch 3: report strengths and skills-coverage scoring.

Issue A -- ReportGenerator emitted positive claims no evidence supported, and
     declared "no evidence" in wording that disagreed with the rest of the
     system. Two distinct paths were affected:
       * overall < 40: the model's grounded insufficiency statement was thrown
         away and replaced by a differently-worded literal;
       * overall >= 40 with no strength the scores support: the report claimed
         "Demonstrated foundational technical knowledge in answered topics."
         even when no topic reached 6.0 and no rubric dimension reached 5.5.

Issue B -- JobMatchingEngine capped the *skills* breakdown component at 85, so a
     candidate holding every required skill was reported as an 85% skills match
     with an empty missing_skills list. The component now reports measured
     coverage; the tests below pin coverage at both ends and in between so the
     cap cannot silently return.

Database safety: these tests use the session-scoped throwaway SQLite database
provisioned by backend/conftest.py. Nothing here touches the configured
PostgreSQL database.
"""

import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.db.models import (
    Answer,
    Company,
    Evaluation,
    Interview,
    Question,
    Role,
    User,
)
from app.matching.matcher import JobMatchingEngine
from app.reports import generator as generator_module
from app.reports.generator import ReportGenerator


class _FailingLLM:
    """Stands in for a provider outage so the deterministic path is exercised."""

    async def generate_json(self, *args, **kwargs):
        raise RuntimeError("provider unavailable")


def _use_failing_llm(monkeypatch):
    monkeypatch.setattr(
        generator_module.AIFactory,
        "get_llm_provider",
        staticmethod(lambda *args, **kwargs: _FailingLLM()),
    )


async def _build_interview(session, turns):
    """Persist a completed interview whose evaluations carry the given scores.

    ``turns`` is a list of ``(topic, dimension_score)`` pairs; every rubric
    dimension of that turn is stored at ``dimension_score`` so the resulting
    report scores are exactly predictable.
    """
    tag = uuid.uuid4().hex[:12]
    user = User(
        email=f"batch3_{tag}@example.com",
        hashed_password=get_password_hash("SecurePassword123!"),
        full_name="Batch 3 Candidate",
        role="candidate",
    )
    company = Company(name=f"Batch3_{tag}", slug=f"batch3-{tag}")
    session.add_all([user, company])
    await session.commit()
    await session.refresh(user)
    await session.refresh(company)

    role = Role(
        company_id=company.id,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "FastAPI"],
    )
    session.add(role)
    await session.commit()
    await session.refresh(role)

    interview = Interview(
        candidate_id=user.id,
        company_id=company.id,
        role_id=role.id,
        mode="text",
        duration_minutes=30,
        target_level="entry",
        status="completed",
    )
    session.add(interview)
    await session.commit()
    await session.refresh(interview)

    for topic, score in turns:
        question = Question(
            company_id=company.id,
            role_id=role.id,
            topic=topic,
            question_text=f"Explain {topic}.",
            difficulty="easy",
            question_type="technical",
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)

        answer = Answer(
            interview_id=interview.id,
            question_id=question.id,
            candidate_answer_text=f"An answer about {topic}.",
        )
        session.add(answer)
        await session.commit()
        await session.refresh(answer)

        session.add(Evaluation(
            answer_id=answer.id,
            correctness_score=score,
            relevance_score=score,
            reasoning_score=score,
            depth_score=score,
            communication_score=score,
            overall_question_score=score,
            feedback_text="Deterministic fixture evaluation.",
            evidence=[],
        ))
        await session.commit()

    return interview


# ======================================================================
# Issue A -- strengths must never outrun the evidence
# ======================================================================

@pytest.mark.asyncio
async def test_low_score_report_declares_insufficient_evidence():
    """A weak interview must say the evidence was insufficient, not stay vague."""
    async with AsyncSessionLocal() as session:
        interview = await _build_interview(session, [
            ("Introduction", 0.1),
            ("FastAPI Concurrency", 0.1),
        ])
        report = await ReportGenerator(session).generate_interview_report(interview.id)

    assert report.overall_score < 40.0
    assert len(report.strengths) > 0
    assert any("insufficient" in s.lower() for s in report.strengths)
    assert not any("demonstrated" in s.lower() and "insufficient" not in s.lower()
                   for s in report.strengths)


@pytest.mark.asyncio
async def test_unsupported_strength_is_not_invented_when_provider_fails(monkeypatch):
    """Scores above the threshold but below every strength bar earn no claim.

    Every rubric dimension is 5.0: over the 40/100 reporting threshold, under
    the 5.5 rubric bar and the 6.0 topic bar. Nothing is demonstrated, so
    nothing may be claimed.
    """
    _use_failing_llm(monkeypatch)

    async with AsyncSessionLocal() as session:
        interview = await _build_interview(session, [
            ("Database Indexing", 5.0),
            ("FastAPI Concurrency", 5.0),
        ])
        report = await ReportGenerator(session).generate_interview_report(interview.id)

    assert report.overall_score == 50.0
    assert all(s < 6.0 for s in report.topic_scores.values())
    assert len(report.strengths) > 0
    assert any("insufficient" in s.lower() for s in report.strengths)
    assert not any("demonstrated foundational technical knowledge" in s.lower()
                   for s in report.strengths)


@pytest.mark.asyncio
async def test_genuine_strengths_survive_for_a_strong_candidate(monkeypatch):
    """The honest-reporting fix must not strip strengths the scores support."""
    _use_failing_llm(monkeypatch)

    async with AsyncSessionLocal() as session:
        interview = await _build_interview(session, [
            ("Database Indexing", 8.5),
            ("System Design", 8.5),
        ])
        report = await ReportGenerator(session).generate_interview_report(interview.id)

    assert report.overall_score == 85.0
    assert len(report.strengths) > 0
    assert not any("insufficient" in s.lower() for s in report.strengths)
    assert any("Database Indexing" in s or "System Design" in s for s in report.strengths)


# ======================================================================
# Issue B -- the skills component must report measured coverage
# ======================================================================

def _role(required_skills):
    return Role(
        id=9001,
        company_id=1,
        title="Backend Engineer",
        level="Entry / L3",
        required_skills=required_skills,
        key_topics=["APIs"],
    )


def _match(candidate_skills, required_skills):
    return JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level="entry",
        candidate_education=[{"degree": "B.Tech in Computer Science"}],
        candidate_projects=[{"name": "API Service", "technologies": ["Python"]}],
        role=_role(required_skills),
    )


def test_full_skill_coverage_reports_a_complete_skills_score():
    result = _match(
        ["Python", "FastAPI", "Docker", "SQL"],
        ["Python", "FastAPI", "Docker", "SQL"],
    )
    assert result["missing_skills"] == []
    assert result["breakdown"]["skills_score"] == 100.0


@pytest.mark.parametrize("candidate_skills,expected", [
    ([], 0.0),
    (["Python"], 25.0),
    (["Python", "FastAPI"], 50.0),
    (["Python", "FastAPI", "Docker"], 75.0),
    (["Python", "FastAPI", "Docker", "SQL"], 100.0),
])
def test_skills_score_equals_measured_coverage(candidate_skills, expected):
    """The component is a measurement, so it must agree with matched/missing."""
    required = ["Python", "FastAPI", "Docker", "SQL"]
    result = _match(candidate_skills, required)

    assert result["breakdown"]["skills_score"] == expected
    assert len(result["matched_skills"]) == len(candidate_skills)
    assert len(result["missing_skills"]) == len(required) - len(candidate_skills)
    coverage = len(result["matched_skills"]) / len(required) * 100.0
    assert result["breakdown"]["skills_score"] == pytest.approx(coverage)
