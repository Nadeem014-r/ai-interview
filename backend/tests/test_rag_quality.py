"""RAG quality: JD extraction, line-aware chunking, exact role association,
relevance-thresholded retrieval, and the source-fact -> prompt grounding chain."""

import uuid
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import create_access_token
from app.ai.base import EmbeddingProvider
from app.db.models import Company, Role, Source, Document, DocumentChunk
from app.rag.chunker import DocumentChunker
from app.rag.rag_engine import RAGEngine
from app.rag.vector_store import VectorStore
from app.research.crawler import CompanyResearchCrawler
from app.research.pipeline import ResearchPipeline
from app.interview.question_selector import QuestionSelector


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


JD_PAGE = """
<html><head><title>Backend Engineer - Acme Pay</title></head><body>
  <nav><a href="/">Home</a><a href="/jobs">Jobs</a></nav>
  <div id="cookie-banner">We use cookies to improve your experience. Accept all</div>
  <main>
    <section class="results">
      <h2>Jobs search results</h2>
      <ul><li><h3>Account Manager, Sales</h3><span>Mumbai</span></li>
          <li><h3>Data Center Technician</h3><span>Pune</span></li></ul>
    </section>
    <section class="detail">
      <h1>Backend Engineer, Payments</h1>
      <div><a>Apply</a></div><div><span>share_outline</span></div>
      <h3>Minimum qualifications:</h3>
      <ul><li>3 years building backend services in Rust.</li></ul>
      <h3>About the job</h3>
      <p>You will join the team that owns Zephyr, the payment ledger service. Zephyr stores every
         transaction in CockroachDB and uses idempotency keys so customers are never charged twice.
         The team designs schemas, tunes transaction isolation, and plans multi-region replication.</p>
      <h3>Responsibilities</h3>
      <ul><li>Design and operate the Zephyr ledger on CockroachDB.</li>
          <li>Review code and debug production incidents in the settlement pipeline.</li></ul>
      <p>Acme Pay is an equal opportunity employer. All qualified applicants will receive consideration.</p>
      <p>Read our privacy policy to learn how applicant data is used.</p>
    </section>
  </main>
  <footer>Copyright 2026 Acme Pay</footer>
</body></html>
"""


# ---------------------------------------------------------------- A. extraction

def test_clean_html_keeps_jd_sections_and_drops_page_noise():
    title, text = CompanyResearchCrawler.clean_html_content(JD_PAGE)
    assert title == "Backend Engineer - Acme Pay"
    for kept in ["Minimum qualifications", "About the job", "Responsibilities",
                 "Zephyr stores every transaction in CockroachDB", "Design and operate the Zephyr ledger"]:
        assert kept in text
    for dropped in ["Account Manager, Sales", "Data Center Technician", "Jobs search results",
                    "cookies", "equal opportunity", "privacy policy", "Copyright", "Apply", "share_outline"]:
        assert dropped not in text


def test_clean_html_without_jd_headings_keeps_whole_page():
    html = "<html><body><h1>Engineering Blog</h1><p>We migrated our queue to Kafka last year.</p></body></html>"
    _, text = CompanyResearchCrawler.clean_html_content(html)
    assert "Engineering Blog" in text and "migrated our queue to Kafka" in text


# ---------------------------------------------------------------- B. chunking

def test_chunk_lines_keeps_whole_lines_and_headings_with_content():
    lines = ["Intro " + "word " * 40, "Responsibilities", "Own the ledger " + "word " * 40, "Tail " + "word " * 40]
    chunks = DocumentChunker.chunk_lines("\n".join(lines), chunk_size=60, overlap=10)
    for chunk in chunks:
        assert len(chunk.split()) <= 60
        for line in chunk.splitlines():
            assert line in [" ".join(l.split()) for l in lines]
    # The heading is never the last line of a chunk; it travels with its content.
    assert not any(c.splitlines()[-1] == "Responsibilities" for c in chunks)
    assert any(c.startswith("Responsibilities\nOwn the ledger") for c in chunks)


def test_chunk_lines_edge_cases():
    assert DocumentChunker.chunk_lines(None) == []
    assert DocumentChunker.chunk_lines("  \n ") == []
    long_line = " ".join(f"w{i}" for i in range(250))
    chunks = DocumentChunker.chunk_lines(long_line, chunk_size=100, overlap=10)
    assert len(chunks) >= 3 and all(len(c.split()) <= 100 for c in chunks)


# ---------------------------------------------------------------- E/G. endpoint

def _admin_headers():
    return {"Authorization": f"Bearer {create_access_token(subject=1, role='admin')}"}


def _ingest_result():
    return {"source": MagicMock(id=1), "document": MagicMock(id=1), "is_cached": False,
            "status": "ingested_new", "content_hash": "h", "chunks_count": 1}


@pytest.mark.asyncio
async def test_research_role_matching_is_exact_and_does_not_duplicate():
    company_name = f"RoleMatch Co {uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        company = Company(name=company_name, slug=company_name.lower().replace(" ", "-"))
        db.add(company)
        await db.commit()
        await db.refresh(company)
        specialised = Role(company_id=company.id, title="Software Engineer (Backend)")
        db.add(specialised)
        await db.commit()
        await db.refresh(specialised)
        company_id, specialised_id = company.id, specialised.id

    body = {"company_name": company_name, "role_title": "software engineer ", "source_url": "https://example.com/jd"}
    with patch.object(ResearchPipeline, "ingest_company_role_research", new=AsyncMock(return_value=_ingest_result())) as ingest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/v1/research/company", json=body, headers=_admin_headers())).status_code == 200
            assert (await client.post("/api/v1/research/company", json=body, headers=_admin_headers())).status_code == 200

    role_ids = {call.kwargs["role_id"] for call in ingest.await_args_list}
    assert len(role_ids) == 1 and specialised_id not in role_ids
    async with AsyncSessionLocal() as db:
        roles = (await db.execute(select(Role).where(Role.company_id == company_id))).scalars().all()
        assert sorted(r.title for r in roles) == ["Software Engineer (Backend)", "software engineer"]


@pytest.mark.asyncio
async def test_research_requires_source_url_and_never_fabricates_one():
    company_name = f"NoUrl Co {uuid.uuid4().hex[:6]}"
    with patch.object(ResearchPipeline, "ingest_company_role_research", new=AsyncMock()) as ingest:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for body in [{"company_name": company_name, "role_title": "SWE"},
                         {"company_name": company_name, "role_title": "SWE", "source_url": "  "}]:
                res = await client.post("/api/v1/research/company", json=body, headers=_admin_headers())
                assert res.status_code == 400
    ingest.assert_not_awaited()
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(Company).where(Company.name == company_name))).scalars().first() is None


# ---------------------------------------------------------------- C/D/F. retrieval + grounding

class KeywordEmbedder(EmbeddingProvider):
    """Deterministic bag-of-keywords embedder, so similarity reflects shared vocabulary."""
    VOCAB = ["cockroachdb", "zephyr", "ledger", "transaction", "database", "idempotency",
             "lunch", "gym", "office", "benefits", "acme", "backend",
             "scylladb", "nimbus", "elixir", "posting", "search"]

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        low = (text or "").lower()
        vec = [float(low.count(word)) for word in self.VOCAB]
        return vec if any(vec) else [1e-6] * len(self.VOCAB)

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]


class CapturingLLM:
    def __init__(self):
        self.prompts: List[str] = []

    async def generate_json(self, prompt, system_prompt=None, **kwargs):
        self.prompts.append(prompt)
        return {"question_text": "How would you design idempotent writes for the Zephyr ledger on CockroachDB?",
                "expected_concepts": ["idempotency keys"], "follow_ups": []}


async def _seed_company_role(db, suffix):
    company = Company(name=f"Acme Pay {suffix}", slug=f"acme-pay-{suffix}")
    db.add(company)
    await db.commit()
    await db.refresh(company)
    role = Role(company_id=company.id, title="Backend Engineer", key_topics=["Relational Databases"])
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return company, role


@pytest.mark.asyncio
async def test_grounding_chain_source_fact_reaches_prompt_and_irrelevant_chunks_are_filtered():
    embedder = KeywordEmbedder()
    suffix = uuid.uuid4().hex[:6]
    fact = "Zephyr stores every transaction in CockroachDB"
    async with AsyncSessionLocal() as db:
        company, role = await _seed_company_role(db, suffix)
        pipeline = ResearchPipeline(db)
        pipeline.vector_store = VectorStore(db, embedder=embedder)
        cleaned_title, cleaned = CompanyResearchCrawler.clean_html_content(
            JD_PAGE + "<p>Benefits: free lunch, gym and a downtown office.</p>")
        crawl = {"cleaned_text": cleaned, "content_hash": CompanyResearchCrawler.compute_content_hash(cleaned),
                 "title": cleaned_title, "extraction_method": "beautifulsoup4"}
        with patch.object(CompanyResearchCrawler, "fetch_page_content", new=AsyncMock(return_value=crawl)):
            result = await pipeline.ingest_company_role_research(company.id, role.id, f"https://example.com/{suffix}")
        assert result["chunks_count"] >= 1

        # source contains fact -> a stored chunk contains fact
        doc = (await db.execute(select(Document).join(Source).where(Source.id == result["source"].id))).scalars().first()
        assert fact in " ".join(doc.content.split())
        hits = await RAGEngine(db, VectorStore(db, embedder=embedder)).retrieve_chunks(
            query="Backend Engineer job responsibilities, qualifications and technologies related to Zephyr ledger on CockroachDB transactions",
            company_id=company.id, role_id=role.id, min_similarity=settings.RAG_MIN_SIMILARITY)
        assert hits and any(fact in " ".join(h["text"].split()) for h in hits)

        # retrieval -> Gemini prompt, with the query built from company/role/topic/type
        selector = QuestionSelector(db)
        selector.rag_engine = RAGEngine(db, VectorStore(db, embedder=embedder))
        spy = AsyncMock(wraps=selector.rag_engine.get_relevant_context)
        selector.rag_engine.get_relevant_context = spy
        llm = CapturingLLM()
        with patch("app.interview.question_selector.AIFactory.get_llm_provider", return_value=llm):
            question = await selector.select_or_generate_question(
                company_id=company.id, role_id=role.id, topic="Zephyr ledger and CockroachDB transactions",
                difficulty="medium", asked_question_ids=[])
        kwargs = spy.await_args.kwargs
        assert kwargs["min_similarity"] == settings.RAG_MIN_SIMILARITY
        for part in ["Backend Engineer", "Zephyr ledger and CockroachDB transactions"]:
            assert part in kwargs["query"]
        assert "<retrieved_knowledge>" in llm.prompts[-1]
        assert fact in " ".join(llm.prompts[-1].split())
        assert "CockroachDB" in question.question_text

        # an unrelated query clears no chunk above the threshold -> no RAG context, fallback notice
        llm2 = CapturingLLM()
        with patch("app.interview.question_selector.AIFactory.get_llm_provider", return_value=llm2):
            await selector.select_or_generate_question(
                company_id=company.id, role_id=role.id, topic="Office gym and lunch perks",
                difficulty="medium", asked_question_ids=[], interview_type="hr")
        assert "<retrieved_knowledge>" not in llm2.prompts[-1]
        assert "None available" in llm2.prompts[-1]


@pytest.mark.asyncio
async def test_no_rag_source_still_generates_question():
    async with AsyncSessionLocal() as db:
        company, role = await _seed_company_role(db, uuid.uuid4().hex[:6])
        llm = CapturingLLM()
        with patch("app.interview.question_selector.AIFactory.get_llm_provider", return_value=llm):
            question = await QuestionSelector(db).select_or_generate_question(
                company_id=company.id, role_id=role.id, topic="Relational Databases",
                difficulty="medium", asked_question_ids=[])
        assert question.id is not None and question.question_text
        prompt = llm.prompts[-1]
        assert "None available" in prompt and "<retrieved_knowledge>" not in prompt
        assert "without presenting any company-specific tech stack" in prompt


NIMBUS_PAGE = """
<html><head><title>Search Engineer - Orbit</title></head><body><nav>Home Jobs</nav><main>
  <h1>Search Engineer, Nimbus</h1>
  <h3>About the job</h3>
  <p>You will work on Nimbus, our full-text search indexer. Nimbus is written in Elixir and stores postings
     in ScyllaDB, partitioned by tenant, and serves ranked results within 50 ms at the 99th percentile.</p>
  <h3>Responsibilities</h3>
  <ul><li>Extend the Nimbus indexing pipeline in Elixir.</li>
      <li>Tune ScyllaDB compaction and partition sizing for posting lists.</li></ul>
</main><footer>Copyright Orbit</footer></body></html>
"""


@pytest.mark.asyncio
async def test_second_fact_grounding_and_source_precedence_in_prompt():
    """Nimbus/ScyllaDB fact survives cleaning, storage and retrieval, and reaches the prompt
    as the authoritative source ranked above the generic role technologies."""
    embedder = KeywordEmbedder()
    fact = "Nimbus is written in Elixir and stores postings in ScyllaDB"
    suffix = uuid.uuid4().hex[:6]
    _, cleaned = CompanyResearchCrawler.clean_html_content(NIMBUS_PAGE)
    assert fact in " ".join(cleaned.split())

    async with AsyncSessionLocal() as db:
        company = Company(name=f"Orbit {suffix}", slug=f"orbit-{suffix}")
        db.add(company)
        await db.commit()
        await db.refresh(company)
        role = Role(company_id=company.id, title="Search Engineer")
        db.add(role)
        await db.commit()
        await db.refresh(role)

        pipeline = ResearchPipeline(db)
        pipeline.vector_store = VectorStore(db, embedder=embedder)
        crawl = {"cleaned_text": cleaned, "content_hash": CompanyResearchCrawler.compute_content_hash(cleaned),
                 "title": "Search Engineer - Orbit", "extraction_method": "beautifulsoup4"}
        with patch.object(CompanyResearchCrawler, "fetch_page_content", new=AsyncMock(return_value=crawl)):
            result = await pipeline.ingest_company_role_research(company.id, role.id, f"https://example.com/{suffix}")
        doc = (await db.execute(select(Document).where(Document.source_id == result["source"].id))).scalars().first()
        chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))).scalars().all()
        assert any(fact in " ".join(c.chunk_text.split()) for c in chunks)

        selector = QuestionSelector(db)
        selector.rag_engine = RAGEngine(db, VectorStore(db, embedder=embedder))
        llm = CapturingLLM()
        with patch("app.interview.question_selector.AIFactory.get_llm_provider", return_value=llm):
            await selector.select_or_generate_question(
                company_id=company.id, role_id=role.id, topic="Nimbus search posting storage in ScyllaDB",
                difficulty="medium", asked_question_ids=[])
        prompt = llm.prompts[-1]
        assert "<retrieved_knowledge>" in prompt and fact in " ".join(prompt.split())
        assert "AUTHORITATIVE source for company/role facts" in prompt
        assert "SOURCE PRECEDENCE: retrieved job description > company/role profile above > your general knowledge" in prompt
        assert "NEVER substitute a generic alternative" in prompt
        assert "Core Technologies (generic role defaults; the retrieved job description below overrides them)" in prompt
        # The job description is placed after the generic defaults it overrides.
        assert prompt.index("Core Technologies (generic") < prompt.index("<retrieved_knowledge>")
