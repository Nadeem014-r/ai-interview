"""Batch 9 regression cover: recurring provider-call cost.

Every assertion here pins a place where the platform could quietly start paying
a provider for work it cannot use. They are cost regressions rather than
functional ones, so nothing else in the suite would catch them.

Issue A -- VectorStore.similarity_search generated the query embedding *before*
    reading the candidate chunks, so a deployment whose corpus is empty (nothing
    ingested for that company/role -- the state of a fresh install, since
    seed_data.py creates no DocumentChunk rows) paid an embedding call on every
    retrieval to score zero chunks. QuestionSelector calls this once per
    interview turn, making it a per-turn charge for a guaranteed-empty result.

Issue B -- ReportGenerator must stay idempotent. The finish endpoint and the
    auto-generation on the final answer turn both call it for the same
    interview, and a lost existing-report guard would mean a second summary
    call per interview.

Issue C -- the configured defaults must not put a paid provider on a path that
    runs every turn, and failover must not bill a second vendor for the same
    request.

Database safety: these tests use the session-scoped throwaway SQLite database
provisioned by backend/conftest.py. Nothing here touches PostgreSQL, and no
real provider is contacted -- every embedder and LLM below is a local double.
"""

import uuid
from typing import Any, Dict, List

import pytest

from app.ai.base import EmbeddingProvider
from app.core.config import Settings
from app.core.database import AsyncSessionLocal
from app.db.models import (
    Answer,
    Company,
    Document,
    DocumentChunk,
    Evaluation,
    Interview,
    Question,
    Role,
    Source,
    User,
)
from app.rag.vector_store import VectorStore
from app.reports import generator as generator_module
from app.reports.generator import ReportGenerator


class CountingEmbedder(EmbeddingProvider):
    """Records how many provider embedding calls a code path would bill for."""

    def __init__(self, dim: int = 8):
        self.embed_text_calls = 0
        self.embed_batch_calls = 0
        self._dim = dim

    async def embed_text(self, text: str) -> List[float]:
        self.embed_text_calls += 1
        return [1.0] + [0.0] * (self._dim - 1)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self.embed_batch_calls += 1
        return [await self.embed_text(t) for t in texts]


class CountingLLM:
    """Counts generate_json calls and returns a well-formed report summary."""

    def __init__(self):
        self.calls = 0

    async def generate_json(self, *args, **kwargs) -> Dict[str, Any]:
        self.calls += 1
        return {
            "strengths": ["Explained request lifecycle accurately"],
            "weaknesses": ["Limited depth on failure modes"],
            "difficult_topics": ["FastAPI Concurrency"],
            "recommendations": ["Review async concurrency trade-offs"],
            "executive_summary": "Counted fixture summary for the cost regression test.",
        }


# ======================================================================
# Issue A -- no embedding call when there is nothing to score
# ======================================================================

@pytest.mark.asyncio
async def test_retrieval_on_empty_corpus_bills_no_embedding():
    """An empty corpus must cost zero provider calls, not one per turn."""
    embedder = CountingEmbedder()
    async with AsyncSessionLocal() as session:
        store = VectorStore(session, embedder=embedder)
        results = await store.similarity_search(
            query="FastAPI concurrency",
            company_id=987654321,   # no Source exists for this company
        )

    assert results == []
    assert embedder.embed_text_calls == 0, (
        "retrieval against an empty corpus must not call the embedding provider"
    )


@pytest.mark.asyncio
async def test_retrieval_with_chunks_still_embeds_and_returns_matches():
    """The saving must not cost retrieval: a populated corpus behaves as before."""
    embedder = CountingEmbedder()
    tag = uuid.uuid4().hex[:12]

    async with AsyncSessionLocal() as session:
        company = Company(name=f"Batch9_{tag}", slug=f"batch9-{tag}")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        source = Source(
            company_id=company.id,
            source_type="official_job_desc",
            source_url=f"https://example.invalid/{tag}",
            title=f"JD {tag}",
            content_hash=tag,
            trust_level="official_trusted",
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        document = Document(
            source_id=source.id,
            title=f"Doc {tag}",
            content="FastAPI handles concurrency with an async event loop.",
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)

        session.add(DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            chunk_text="FastAPI handles concurrency with an async event loop.",
            embedding_json=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ))
        await session.commit()

        store = VectorStore(session, embedder=embedder)
        results = await store.similarity_search(
            query="FastAPI concurrency",
            company_id=company.id,
            min_similarity=0.0,
        )

    assert embedder.embed_text_calls == 1, "a real retrieval still embeds exactly once"
    assert len(results) == 1
    assert "event loop" in results[0]["text"]


# ======================================================================
# Issue B -- one summary call per interview, not one per caller
# ======================================================================

async def _build_completed_interview(session, turns):
    """Persist a completed interview with stored evaluations at the given scores."""
    tag = uuid.uuid4().hex[:12]
    user = User(
        email=f"batch9_{tag}@example.com",
        # A literal placeholder: nothing here authenticates, so the test stays
        # independent of the password-hashing backend.
        hashed_password="not-a-real-hash",
        full_name="Batch 9 Candidate",
        role="candidate",
    )
    company = Company(name=f"Batch9R_{tag}", slug=f"batch9r-{tag}")
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
            evidence=[f"Candidate discussed {topic}."],
        ))
        await session.commit()

    return interview


@pytest.mark.asyncio
async def test_report_generation_is_idempotent_and_bills_once(monkeypatch):
    """finish + auto-generation must not each pay for their own summary."""
    llm = CountingLLM()
    monkeypatch.setattr(
        generator_module.AIFactory,
        "get_llm_provider",
        staticmethod(lambda *args, **kwargs: llm),
    )

    async with AsyncSessionLocal() as session:
        interview = await _build_completed_interview(session, [
            ("FastAPI Concurrency", 7.0),
            ("Databases", 6.5),
        ])

        first = await ReportGenerator(session).generate_interview_report(interview.id)
        second = await ReportGenerator(session).generate_interview_report(interview.id)

    assert first.id == second.id, "the second call must return the stored report"
    assert llm.calls == 1, (
        "report generation must call the LLM once per interview, not once per caller"
    )


@pytest.mark.asyncio
async def test_report_generation_reuses_stored_evaluations(monkeypatch):
    """Reports must read persisted evaluations, never re-run answer evaluation."""
    llm = CountingLLM()
    monkeypatch.setattr(
        generator_module.AIFactory,
        "get_llm_provider",
        staticmethod(lambda *args, **kwargs: llm),
    )

    def _fail(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("report generation must not re-evaluate answers")

    from app.evaluation import evaluator as evaluator_module
    monkeypatch.setattr(evaluator_module.AnswerEvaluator, "evaluate_answer", _fail)

    async with AsyncSessionLocal() as session:
        interview = await _build_completed_interview(session, [("Databases", 8.0)])
        report = await ReportGenerator(session).generate_interview_report(interview.id)

    assert report.overall_score > 0.0
    assert llm.calls == 1


# ======================================================================
# Issue C -- defaults must keep paid providers off the per-turn path
# ======================================================================

def _shipped_default(field_name: str) -> str:
    """The default declared on Settings, independent of any local .env.

    Reading `settings.X` here would assert against whatever the developer's
    environment happens to set, so these tests pin the value the project
    actually ships.
    """
    return str(Settings.model_fields[field_name].default).strip().lower()


def test_llm_fallback_default_is_not_a_paid_provider():
    """Failover exists to keep the demo alive, not to charge a second vendor."""
    assert _shipped_default("LLM_FALLBACK_PROVIDER") in {"mock", ""}, (
        "a paid LLM_FALLBACK_PROVIDER default would bill twice for one request"
    )


def test_default_embedding_provider_is_not_paid():
    """RAG retrieval runs per interview turn; its default must stay free."""
    assert _shipped_default("DEFAULT_EMBEDDING_PROVIDER") == "mock", (
        "a paid embedding default turns every interview turn into a billed call"
    )


def test_default_voice_providers_are_local():
    """Local STT/TTS keeps per-minute speech billing out of the default path."""
    assert _shipped_default("DEFAULT_STT_PROVIDER") == "whisper"
    assert _shipped_default("DEFAULT_TTS_PROVIDER") == "kokoro"
