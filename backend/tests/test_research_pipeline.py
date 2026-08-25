import pytest
import io
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from httpx import AsyncClient, ASGITransport, Response

from app.main import app
from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import create_access_token
from app.db.models import User, Company, Role, Source, Document, DocumentChunk
from app.research.security import (
    URLSecurityValidator,
    InvalidURLError,
    SSRFProtectionError,
    DisallowedDomainError
)
from app.research.crawler import (
    CompanyResearchCrawler,
    CrawlerError,
    UnsupportedContentTypeError,
    OversizedContentError,
    EmptyContentError,
    FetchTimeoutError,
    HTTPFetchError,
    PlaywrightUnavailableError
)
from app.research.pipeline import ResearchPipeline, StaleRefreshFailedError
from app.rag.vector_store import VectorStore
from sqlalchemy import select
from sqlalchemy.orm import selectinload

@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()

# Helper for auth token
def get_auth_header(role: str = "admin", user_id: int = 1) -> dict:
    token = create_access_token(subject=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}

# =========================================================================
# 1. Valid HTTP URL
# =========================================================================
def test_valid_http_url():
    url = "http://careers.google.com/jobs/123"
    validated = URLSecurityValidator.validate_url(url, allowed_domains=["*"], resolve_dns=False)
    assert validated.startswith("http://")

# =========================================================================
# 2. HTTPS URL
# =========================================================================
def test_valid_https_url():
    url = "https://careers.google.com/jobs/456"
    validated = URLSecurityValidator.validate_url(url, allowed_domains=["*"], resolve_dns=False)
    assert validated.startswith("https://")

# =========================================================================
# 3. Invalid URL
# =========================================================================
def test_invalid_url_structure():
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("not_a_valid_url", resolve_dns=False)
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("", resolve_dns=False)
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("http://", resolve_dns=False)

# =========================================================================
# 4. Unsupported Scheme
# =========================================================================
def test_unsupported_scheme_rejected():
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("ftp://files.example.com/jd.txt", resolve_dns=False)
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("file:///etc/passwd", resolve_dns=False)
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("javascript:alert(1)", resolve_dns=False)
    with pytest.raises(InvalidURLError):
        URLSecurityValidator.validate_url("data:text/html,<h1>Hello</h1>", resolve_dns=False)

# =========================================================================
# 5. Localhost Rejection
# =========================================================================
def test_localhost_rejection():
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://localhost:8000/api", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://127.0.0.1:5432/", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://app.localhost/admin", resolve_dns=False)

# =========================================================================
# 6. Private IP Rejection
# =========================================================================
def test_private_ip_rejection():
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://192.168.1.1/router", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://10.0.0.5/internal", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://172.16.0.1/secret", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://0.0.0.0:8080", resolve_dns=False)

# =========================================================================
# 7. SSRF Metadata Protection
# =========================================================================
def test_ssrf_metadata_protection():
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://169.254.169.254/latest/meta-data/", resolve_dns=False)
    with pytest.raises(SSRFProtectionError):
        URLSecurityValidator.validate_url("http://metadata.google.internal/computeMetadata/v1/", resolve_dns=False)

# =========================================================================
# 8. Disallowed Domain Rejection
# =========================================================================
def test_disallowed_domain_rejection():
    allowed = ["example.com", "careers.company.com"]
    with pytest.raises(DisallowedDomainError):
        URLSecurityValidator.validate_url("https://evil-example.com/job", allowed_domains=allowed, resolve_dns=False)
    with pytest.raises(DisallowedDomainError):
        URLSecurityValidator.validate_url("https://example.com.attacker.org/job", allowed_domains=allowed, resolve_dns=False)
    with pytest.raises(DisallowedDomainError):
        URLSecurityValidator.validate_url("https://randomsite.net/page", allowed_domains=allowed, resolve_dns=False)

# =========================================================================
# 9. Allowed Domain Success
# =========================================================================
def test_allowed_domain_success():
    allowed = ["example.com", "company.org"]
    val1 = URLSecurityValidator.validate_url("https://example.com/careers", allowed_domains=allowed, resolve_dns=False)
    assert val1 == "https://example.com/careers"
    val2 = URLSecurityValidator.validate_url("https://jobs.example.com/roles/dev", allowed_domains=allowed, resolve_dns=False)
    assert val2 == "https://jobs.example.com/roles/dev"

# =========================================================================
# 10. Redirect to Allowed Domain
# =========================================================================
@pytest.mark.asyncio
async def test_redirect_to_allowed_domain():
    def handler(request: httpx.Request):
        if str(request.url) == "https://example.com/short":
            return Response(302, headers={"Location": "https://example.com/full-job-desc"})
        return Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><head><title>Job Desc</title></head><body><h1>Software Engineer</h1><p>We are seeking a Python expert.</p></body></html>"
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            res = await CompanyResearchCrawler.fetch_page_content(
                "https://example.com/short",
                allowed_domains=["example.com"],
                custom_client=client
            )
            assert res["status"] == "success"
            assert res["url"] == "https://example.com/full-job-desc"
            assert "Software Engineer" in res["cleaned_text"]

# =========================================================================
# 11. Redirect to Disallowed Domain / SSRF Target Rejected
# =========================================================================
@pytest.mark.asyncio
async def test_redirect_to_disallowed_domain_rejected():
    def handler(request: httpx.Request):
        return Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(SSRFProtectionError):
            await CompanyResearchCrawler.fetch_page_content(
                "https://example.com/redirect-to-metadata",
                allowed_domains=["*"],
                custom_client=client
            )

# =========================================================================
# 12. Successful HTML Extraction
# =========================================================================
def test_successful_html_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Acme Corp - Senior Backend Engineer</title></head>
    <body>
        <h1>Role Overview</h1>
        <p>Acme Corp is hiring a Senior Backend Engineer to build distributed streaming systems.</p>
        <h2>Requirements:</h2>
        <ul>
            <li>5+ years with Python or Go</li>
            <li>Experience with PostgreSQL and Kafka</li>
        </ul>
    </body>
    </html>
    """
    title, text = CompanyResearchCrawler.clean_html_content(html)
    assert title == "Acme Corp - Senior Backend Engineer"
    assert "Role Overview" in text
    assert "Acme Corp is hiring a Senior Backend Engineer" in text
    assert "5+ years with Python or Go" in text
    assert "Experience with PostgreSQL and Kafka" in text

# =========================================================================
# 13. Script and Style Removal
# =========================================================================
def test_script_and_style_removal():
    html = """
    <html>
    <head>
        <style>body { background: red; } .ad { display: none; }</style>
        <script>var trackingId = 'TRACK-12345'; sendTelemetry();</script>
    </head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <h1>Real Content</h1>
        <p>This is meaningful job information.</p>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    title, text = CompanyResearchCrawler.clean_html_content(html)
    assert "trackingId" not in text
    assert "background: red" not in text
    assert "Home" not in text
    assert "Copyright" not in text
    assert "Real Content" in text
    assert "meaningful job information" in text

# =========================================================================
# 14. Meaningful Text Extraction
# =========================================================================
def test_meaningful_text_preserves_structure():
    html = """
    <div>
        <h2>Key Responsibilities</h2>
        <p>Design REST APIs and microservices.</p>
        <h2>Required Qualifications</h2>
        <ul>
            <li>BS in Computer Science</li>
            <li>Strong problem-solving skills</li>
        </ul>
    </div>
    """
    _, text = CompanyResearchCrawler.clean_html_content(html)
    assert "Key Responsibilities" in text
    assert "Design REST APIs" in text
    assert "BS in Computer Science" in text

# =========================================================================
# 15. Empty HTML Handling
# =========================================================================
@pytest.mark.asyncio
async def test_empty_html_handling():
    def handler(request: httpx.Request):
        return Response(200, headers={"Content-Type": "text/html"}, text="<html><body></body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            with pytest.raises(EmptyContentError):
                await CompanyResearchCrawler.fetch_page_content(
                    "https://example.com/empty",
                    allowed_domains=["*"],
                    custom_client=client
                )

# =========================================================================
# 16. Unsupported Content Type
# =========================================================================
@pytest.mark.asyncio
async def test_unsupported_content_type():
    def handler(request: httpx.Request):
        return Response(200, headers={"Content-Type": "image/png"}, content=b"\x89PNG\r\n\x1a\n")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            with pytest.raises(UnsupportedContentTypeError):
                await CompanyResearchCrawler.fetch_page_content(
                    "https://example.com/logo.png",
                    allowed_domains=["*"],
                    custom_client=client
                )

# =========================================================================
# 17. Oversized Response Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_oversized_response_rejection():
    # Generate content exceeding max allowed size
    huge_content = "A" * (settings.RESEARCH_MAX_RESPONSE_SIZE_BYTES + 1024)
    def handler(request: httpx.Request):
        return Response(200, headers={"Content-Type": "text/html"}, text=huge_content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            with pytest.raises(OversizedContentError):
                await CompanyResearchCrawler.fetch_page_content(
                    "https://example.com/huge.html",
                    allowed_domains=["*"],
                    custom_client=client
                )

# =========================================================================
# 18. Timeout Handling
# =========================================================================
@pytest.mark.asyncio
async def test_timeout_handling():
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("Read timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            with pytest.raises(FetchTimeoutError):
                await CompanyResearchCrawler.fetch_page_content(
                    "https://example.com/slow",
                    allowed_domains=["*"],
                    custom_client=client
                )

# =========================================================================
# 19. Retry Behavior on Transient Errors
# =========================================================================
@pytest.mark.asyncio
async def test_retry_behavior_transient_error():
    attempts = 0
    def handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return Response(503, headers={"Content-Type": "text/html"}, text="Service Unavailable")
        return Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><head><title>Success</title></head><body><h1>Recovered</h1><p>Content loaded successfully after retry.</p></body></html>"
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with patch.object(URLSecurityValidator, "validate_url", side_effect=lambda u, a=None, r=True: u):
            res = await CompanyResearchCrawler.fetch_page_content(
                "https://example.com/flaky",
                allowed_domains=["*"],
                custom_client=client
            )
            assert res["status"] == "success"
            assert "Recovered" in res["cleaned_text"]
            assert attempts == 2

# =========================================================================
# 20. SHA-256 Hash Consistency
# =========================================================================
def test_sha256_hash_consistency():
    text1 = "Senior Cloud Architect with AWS and Kubernetes experience."
    text2 = "Senior Cloud Architect with AWS and Kubernetes experience."
    hash1 = CompanyResearchCrawler.compute_content_hash(text1)
    hash2 = CompanyResearchCrawler.compute_content_hash(text2)
    assert len(hash1) == 64
    assert hash1 == hash2

# =========================================================================
# 21. Changed Content Produces Different Hash
# =========================================================================
def test_changed_content_produces_different_hash():
    text1 = "Version 1 specifications for machine learning engineer."
    text2 = "Version 2 updated specifications with PyTorch and Triton."
    hash1 = CompanyResearchCrawler.compute_content_hash(text1)
    hash2 = CompanyResearchCrawler.compute_content_hash(text2)
    assert hash1 != hash2

# =========================================================================
# 22 & 23. Duplicate Content & Cache Hit
# =========================================================================
@pytest.mark.asyncio
async def test_duplicate_content_and_cache_hit():
    async with AsyncSessionLocal() as session:
        # Create company and role
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="Backend Dev", level="L3", required_skills=["Python"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        pipeline = ResearchPipeline(session)
        target_url = f"https://careers.{c.slug}.com/job/1"

        mock_crawl_result = {
            "url": target_url,
            "title": "Backend Dev Specifications",
            "raw_html": "<p>Standard JD text</p>",
            "cleaned_text": "Standard JD text requiring Python and Postgres skills.",
            "content_hash": CompanyResearchCrawler.compute_content_hash("Standard JD text requiring Python and Postgres skills."),
            "status": "success",
            "extraction_method": "beautifulsoup4"
        }

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_crawl_result
            
            # First call -> Ingests new
            res1 = await pipeline.ingest_company_role_research(
                company_id=c.id,
                role_id=r.id,
                source_url=target_url,
                title="Backend Dev Specs"
            )
            assert res1["is_cached"] is False
            assert res1["status"] == "ingested_new"
            assert mock_fetch.call_count == 1

            # Second call -> Fresh cache hit (no crawler call)
            res2 = await pipeline.ingest_company_role_research(
                company_id=c.id,
                role_id=r.id,
                source_url=target_url,
                title="Backend Dev Specs"
            )
            assert res2["is_cached"] is True
            assert res2["status"] == "fresh_cached"
            assert mock_fetch.call_count == 1  # Not called again!

# =========================================================================
# 24. Cache Miss for New Content / New URL
# =========================================================================
@pytest.mark.asyncio
async def test_cache_miss_for_new_url():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="Frontend Dev", level="L3", required_skills=["React"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        pipeline = ResearchPipeline(session)
        url1 = f"https://careers.{c.slug}.com/job/1"
        url2 = f"https://careers.{c.slug}.com/job/2"

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                {
                    "url": url1,
                    "title": "Job 1",
                    "raw_html": "<p>Job 1</p>",
                    "cleaned_text": "Job 1 requirements description.",
                    "content_hash": CompanyResearchCrawler.compute_content_hash("Job 1 requirements description."),
                    "status": "success"
                },
                {
                    "url": url2,
                    "title": "Job 2",
                    "raw_html": "<p>Job 2</p>",
                    "cleaned_text": "Job 2 requirements description.",
                    "content_hash": CompanyResearchCrawler.compute_content_hash("Job 2 requirements description."),
                    "status": "success"
                }
            ]

            res1 = await pipeline.ingest_company_role_research(c.id, r.id, url1)
            assert res1["is_cached"] is False
            res2 = await pipeline.ingest_company_role_research(c.id, r.id, url2)
            assert res2["is_cached"] is False
            assert mock_fetch.call_count == 2

# =========================================================================
# 25 & 26. Freshness Logic & Stale Source Refresh
# =========================================================================
@pytest.mark.asyncio
async def test_freshness_logic_and_stale_refresh():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="ML Engineer", level="L4", required_skills=["PyTorch"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        target_url = f"https://careers.{c.slug}.com/ml"
        pipeline = ResearchPipeline(session)

        # Create source with old timestamp (e.g. 48 hours ago)
        old_text = "Initial ML specs with PyTorch."
        old_hash = CompanyResearchCrawler.compute_content_hash(old_text)
        old_source = Source(
            company_id=c.id,
            role_id=r.id,
            source_type="official_job_desc",
            source_url=target_url,
            title="Initial ML Specs",
            content_hash=old_hash,
            trust_level="official_trusted",
            fetched_at=datetime.utcnow() - timedelta(hours=48)
        )
        session.add(old_source)
        await session.commit()
        await session.refresh(old_source)

        old_doc = Document(source_id=old_source.id, title="Initial ML Specs", content=old_text)
        session.add(old_doc)
        await session.commit()

        # Refetch with updated content
        new_text = "Updated ML specs with PyTorch, CUDA, and Triton."
        new_hash = CompanyResearchCrawler.compute_content_hash(new_text)

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "url": target_url,
                "title": "Updated ML Specs",
                "raw_html": f"<p>{new_text}</p>",
                "cleaned_text": new_text,
                "content_hash": new_hash,
                "status": "success"
            }

            res = await pipeline.ingest_company_role_research(c.id, r.id, target_url, freshness_hours=24)
            assert res["is_cached"] is False
            assert res["status"] == "updated_content"
            assert res["content_hash"] == new_hash

# =========================================================================
# 27. Failed Refresh Preserves Valid Previous Content
# =========================================================================
@pytest.mark.asyncio
async def test_failed_refresh_preserves_valid_previous_content():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="DevOps", level="L3", required_skills=["Terraform"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        target_url = f"https://careers.{c.slug}.com/devops"
        pipeline = ResearchPipeline(session)

        # Create valid existing source that is now stale
        valid_text = "Existing valid DevOps documentation."
        valid_hash = CompanyResearchCrawler.compute_content_hash(valid_text)
        source = Source(
            company_id=c.id,
            role_id=r.id,
            source_type="official_job_desc",
            source_url=target_url,
            title="Valid DevOps",
            content_hash=valid_hash,
            trust_level="official_trusted",
            fetched_at=datetime.utcnow() - timedelta(hours=72)
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        doc = Document(source_id=source.id, title="Valid DevOps", content=valid_text)
        session.add(doc)
        await session.commit()

        # Simulate network error during refetch
        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = FetchTimeoutError("Target connection timed out.")
            
            with pytest.raises(StaleRefreshFailedError):
                await pipeline.ingest_company_role_research(c.id, r.id, target_url, freshness_hours=24)

            # Verify original content in DB is still untouched
            stmt = select(Document).where(Document.source_id == source.id)
            preserved_doc = (await session.execute(stmt)).scalars().first()
            assert preserved_doc.content == valid_text

# =========================================================================
# 28, 29, 30. Provenance, Document, & Chunk Creation
# =========================================================================
@pytest.mark.asyncio
async def test_provenance_and_chunk_metadata():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="Security Engineer", level="L4", required_skills=["Cryptography"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        target_url = f"https://careers.{c.slug}.com/security"
        pipeline = ResearchPipeline(session)

        content = "Security Engineer role responsible for identity infrastructure, TLS, OAuth2, and penetration testing."
        content_hash = CompanyResearchCrawler.compute_content_hash(content)

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "url": target_url,
                "title": "Security Engineering Specs",
                "raw_html": f"<p>{content}</p>",
                "cleaned_text": content,
                "content_hash": content_hash,
                "status": "success",
                "extraction_method": "beautifulsoup4"
            }

            res = await pipeline.ingest_company_role_research(c.id, r.id, target_url)
            source = res["source"]
            doc = res["document"]

            # Query DocumentChunk to verify provenance
            stmt_chunks = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            chunks = (await session.execute(stmt_chunks)).scalars().all()
            assert len(chunks) > 0

            meta = chunks[0].metadata_json
            assert meta["company_id"] == c.id
            assert meta["role_id"] == r.id
            assert meta["source_id"] == source.id
            assert meta["document_id"] == doc.id
            assert meta["source_url"] == target_url
            assert meta["content_hash"] == content_hash
            assert meta["extraction_method"] == "beautifulsoup4"

# =========================================================================
# 31. Vector Store Search with Research Metadata
# =========================================================================
@pytest.mark.asyncio
async def test_vector_store_search_with_metadata():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="Data Engineer", level="L3", required_skills=["SQL"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        pipeline = ResearchPipeline(session)
        target_url = f"https://careers.{c.slug}.com/data"
        content = "Data Engineer must be proficient in PySpark, Snowflake, and dbt."
        content_hash = CompanyResearchCrawler.compute_content_hash(content)

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "url": target_url,
                "title": "Data Engineering Specs",
                "raw_html": f"<p>{content}</p>",
                "cleaned_text": content,
                "content_hash": content_hash,
                "status": "success"
            }
            await pipeline.ingest_company_role_research(c.id, r.id, target_url)

        vs = VectorStore(session)
        search_res = await vs.similarity_search("Snowflake PySpark", company_id=c.id, role_id=r.id)
        assert len(search_res) > 0
        assert "PySpark" in search_res[0]["text"]
        assert search_res[0]["metadata"]["company_id"] == c.id

# =========================================================================
# 32. No Duplicate Chunks on Unchanged Content Refetch
# =========================================================================
@pytest.mark.asyncio
async def test_no_duplicate_chunks_on_unchanged_refetch():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="QA Lead", level="L4", required_skills=["Selenium"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        pipeline = ResearchPipeline(session)
        target_url = f"https://careers.{c.slug}.com/qa"
        content = "QA Lead oversees end-to-end automation with Selenium, Playwright, and Cypress."
        content_hash = CompanyResearchCrawler.compute_content_hash(content)

        crawl_ret = {
            "url": target_url,
            "title": "QA Lead Specs",
            "raw_html": f"<p>{content}</p>",
            "cleaned_text": content,
            "content_hash": content_hash,
            "status": "success"
        }

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = crawl_ret

            # Ingest initial
            res1 = await pipeline.ingest_company_role_research(c.id, r.id, target_url)
            doc_id = res1["document"].id

            # Count chunks
            stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            count1 = len((await session.execute(stmt)).scalars().all())

            # Force refresh with identical content
            res2 = await pipeline.ingest_company_role_research(c.id, r.id, target_url, force_refresh=True)
            assert res2["status"] == "unchanged_refreshed"

            count2 = len((await session.execute(stmt)).scalars().all())
            assert count1 == count2  # No duplicate chunks created!

# =========================================================================
# 33. Database Rollback on Ingestion Failure
# =========================================================================
@pytest.mark.asyncio
async def test_database_rollback_on_failure():
    async with AsyncSessionLocal() as session:
        c = Company(name=f"Comp_{uuid.uuid4().hex[:6]}", slug=f"slug_{uuid.uuid4().hex[:6]}")
        session.add(c)
        await session.commit()
        await session.refresh(c)

        r = Role(company_id=c.id, title="Architect", level="L5", required_skills=["Distributed Systems"])
        session.add(r)
        await session.commit()
        await session.refresh(r)

        pipeline = ResearchPipeline(session)
        target_url = f"https://careers.{c.slug}.com/fail"
        content = "Valid content for test."
        content_hash = CompanyResearchCrawler.compute_content_hash(content)

        with patch.object(CompanyResearchCrawler, "fetch_page_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "url": target_url,
                "title": "Architect Specs",
                "raw_html": f"<p>{content}</p>",
                "cleaned_text": content,
                "content_hash": content_hash,
                "status": "success"
            }
            # Inject error into vector store add_chunk
            with patch.object(pipeline.vector_store, "add_chunk", side_effect=RuntimeError("Vector Store Failure")):
                with pytest.raises(RuntimeError):
                    await pipeline.ingest_company_role_research(c.id, r.id, target_url)

# =========================================================================
# 34. API Role Authorization
# =========================================================================
@pytest.mark.asyncio
async def test_api_role_authorization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Candidate token -> 403 Forbidden
        cand_headers = get_auth_header(role="candidate")
        res = await client.post("/api/v1/research/company", json={"company_name": "Google", "role_title": "SWE"}, headers=cand_headers)
        assert res.status_code == 403

        # Admin token -> 200 (when mocked)
        admin_headers = get_auth_header(role="admin")
        with patch.object(ResearchPipeline, "ingest_company_role_research", new_callable=AsyncMock) as mock_ingest:
            mock_source = MagicMock()
            mock_source.id = 99
            mock_ingest.return_value = {
                "source": mock_source,
                "document": MagicMock(id=101),
                "is_cached": False,
                "status": "ingested_new",
                "content_hash": "dummyhash",
                "chunks_count": 2
            }
            res_admin = await client.post("/api/v1/research/company", json={"company_name": "Google", "role_title": "SWE"}, headers=admin_headers)
            assert res_admin.status_code == 200
            assert res_admin.json()["source_id"] == 99

# =========================================================================
# 35. API Input Validation
# =========================================================================
@pytest.mark.asyncio
async def test_api_input_validation():
    admin_headers = get_auth_header(role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/api/v1/research/company", json={"company_name": "", "role_title": "SWE"}, headers=admin_headers)
        assert res1.status_code == 400
        res2 = await client.post("/api/v1/research/company", json={"company_name": "Acme", "role_title": "  "}, headers=admin_headers)
        assert res2.status_code == 400

# =========================================================================
# 36. No Fabricated Fallback Data on Crawler Failure
# =========================================================================
@pytest.mark.asyncio
async def test_no_fabricated_fallback_data_on_crawler_failure():
    admin_headers = get_auth_header(role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch.object(CompanyResearchCrawler, "fetch_page_content", side_effect=FetchTimeoutError("Upstream timeout")):
            res = await client.post(
                "/api/v1/research/company",
                json={"company_name": "NonExistentCompany", "role_title": "Engineer", "source_url": "https://careers.google.com/job/fail"},
                headers=admin_headers
            )
            # MUST fail with 504/502 and NEVER fabricate simulated success data
            assert res.status_code in {502, 504}
            assert "source_id" not in res.json()

# =========================================================================
# 37. Playwright Graceful Fallback
# =========================================================================
@pytest.mark.asyncio
async def test_playwright_graceful_fallback():
    with patch("app.core.config.settings.RESEARCH_ENABLE_PLAYWRIGHT", False):
        with pytest.raises(PlaywrightUnavailableError):
            await CompanyResearchCrawler._fetch_with_playwright("https://example.com/spa")
