"""Module 2A: Live JD Scraping Service with 24h Redis Cache.

Fetches job descriptions from:
  1. Jina Reader API (free, clean text, primary)
  2. Greenhouse API (structured JSON for supported companies)
  3. httpx + BeautifulSoup4 (fallback for any public career URL)

Cache key: jd:{company_slug}:{role_slug} with 86400s TTL.
"""

from __future__ import annotations

import re
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.schemas.taxonomy import ScrapingResult

logger = logging.getLogger("ai_interviewer.jd_scraper")

# ---------------------------------------------------------------------------
# Company slug → Greenhouse board slug mapping for pre-configured companies.
# Add entries here as more companies are onboarded.
# ---------------------------------------------------------------------------
GREENHOUSE_BOARDS: Dict[str, str] = {
    "google": "google",
    "meta": "meta",
    "amazon": "amazon",
    "microsoft": "microsoft",
    "apple": "apple",
    "netflix": "netflix",
    "openai": "openai",
    "anthropic": "anthropic",
    "databricks": "databricks",
    "stripe": "stripe",
    "airbnb": "airbnb",
    "uber": "uber",
    "lyft": "lyft",
    "shopify": "shopify",
}

# Skill extraction patterns for JD text
_SKILL_SECTION_HEADERS = re.compile(
    r"(?:required|qualifications?|must.have|skills?|experience|expertise|"
    r"what\s+we'?re?\s+looking\s+for|requirements?|you\s+(?:have|bring|need))",
    re.IGNORECASE,
)

# Common tech terms used as anchors for extraction
_TECH_ANCHOR_PATTERN = re.compile(
    r"\b("
    r"Python|Java(?:Script|)?|TypeScript|Go(?:lang)?|Rust|C\+\+|C#|Kotlin|Swift|Scala|"
    r"React|Next\.js|Vue|Angular|Node\.js|FastAPI|Django|Flask|Spring|"
    r"PyTorch|TensorFlow|Keras|Scikit.Learn|Pandas|NumPy|Transformers|"
    r"LangChain|HuggingFace|RAG|LLM|RL(?:HF)?|Vector\s*(?:DB|Database|Embedding)|"
    r"AWS|GCP|Azure|Docker|Kubernetes|K8s|Terraform|CI/?CD|Linux|"
    r"PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|DynamoDB|"
    r"GraphQL|gRPC|WebSocket|REST(?:ful)?|Microservice|"
    r"NLP|Computer\s*Vision|MLOps|Data\s*Engineering|"
    r"SQL|NoSQL|Spark|Kafka|Airflow|dbt|"
    r"Machine\s*Learning|Deep\s*Learning|Neural\s*Network"
    r")\b",
    re.IGNORECASE,
)


def _extract_skills_from_jd_text(jd_text: str) -> Tuple[List[str], List[str]]:
    """
    Extract required and nice-to-have skills from raw JD text.
    Returns (required_skills, nice_to_have_skills).
    """
    lines = jd_text.splitlines()
    required: List[str] = []
    nice_to_have: List[str] = []

    in_required = False
    in_nice = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # Detect section transitions
        if re.search(r"\b(?:required|must.have|qualifications?|requirements?)\b", lower):
            in_required = True
            in_nice = False
            continue
        if re.search(r"\b(?:nice.to.have|preferred|plus|bonus|optional)\b", lower):
            in_nice = True
            in_required = False
            continue
        if re.search(r"^\s*#+\s+", stripped) or re.search(r"^(?:about|we\s+offer|benefits?|perks?)\b", lower):
            in_required = False
            in_nice = False

        # Extract tech mentions
        matches = _TECH_ANCHOR_PATTERN.findall(stripped)
        for m in matches:
            canonical = m.strip()
            if in_nice:
                if canonical not in nice_to_have:
                    nice_to_have.append(canonical)
            else:
                if canonical not in required:
                    required.append(canonical)

    # If section-based extraction found nothing, fall back to global scan
    if not required:
        all_matches = list(dict.fromkeys(_TECH_ANCHOR_PATTERN.findall(jd_text)))
        required = all_matches[:30]

    return required, nice_to_have


def _slugify(text: str) -> str:
    """Convert text to a safe cache key slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-")[:60]


class JDCache:
    """Redis-backed JD cache with graceful no-Redis fallback."""

    _in_memory: Dict[str, Dict[str, Any]] = {}  # fallback when Redis unavailable
    _TTL_SECONDS = 86400  # 24 hours

    @classmethod
    async def get(cls, key: str) -> Optional[Dict[str, Any]]:
        try:
            import redis.asyncio as aioredis
            from app.core.config import settings
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            async with client:
                val = await client.get(f"jd:{key}")
                if val:
                    return json.loads(val)
        except Exception:
            pass

        # In-memory fallback
        entry = cls._in_memory.get(key)
        if entry:
            cached_at = entry.get("_cached_at", 0)
            import time
            if time.time() - cached_at < cls._TTL_SECONDS:
                return entry
        return None

    @classmethod
    async def set(cls, key: str, data: Dict[str, Any]) -> None:
        import time
        data_with_ts = {**data, "_cached_at": time.time()}
        try:
            import redis.asyncio as aioredis
            from app.core.config import settings
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            async with client:
                await client.setex(
                    f"jd:{key}",
                    cls._TTL_SECONDS,
                    json.dumps(data_with_ts, default=str),
                )
        except Exception:
            pass
        cls._in_memory[key] = data_with_ts

    @classmethod
    async def get_previous_skills(cls, key: str) -> List[str]:
        """Fetch the required_skills list from the *previous* cached snapshot (for delta detection)."""
        entry = await cls.get(key)
        if entry:
            return entry.get("required_skills", [])
        return []


class JDScrapingService:
    """
    Asynchronous JD scraper with Jina Reader → Greenhouse → BS4 fallback chain.
    Results are cached in Redis (or in-memory) for 24 hours.
    """

    JINA_BASE = "https://r.jina.ai/"
    GREENHOUSE_BASE = "https://boards.greenhouse.io/api/v1/boards"
    REQUEST_TIMEOUT = 15.0

    @classmethod
    async def scrape(
        cls,
        company_name: str,
        role_title: str,
        jd_url: Optional[str] = None,
    ) -> ScrapingResult:
        """
        Main entry point. Returns a ScrapingResult with extracted skills.
        Checks cache first; fetches fresh data if stale.
        """
        company_slug = _slugify(company_name)
        role_slug = _slugify(role_title)
        cache_key = f"{company_slug}:{role_slug}"

        # Check cache
        cached = await JDCache.get(cache_key)
        if cached:
            logger.info(f"JD cache hit: {cache_key}")
            try:
                result = ScrapingResult(**{k: v for k, v in cached.items() if not k.startswith("_")})
                result.cached = True
                return result
            except Exception:
                pass

        # Fetch fresh data
        result = await cls._fetch_with_fallback(
            company_name=company_name,
            company_slug=company_slug,
            role_title=role_title,
            role_slug=role_slug,
            jd_url=jd_url,
        )

        # Store in cache
        await JDCache.set(cache_key, result.model_dump())
        return result

    @classmethod
    async def _fetch_with_fallback(
        cls,
        company_name: str,
        company_slug: str,
        role_title: str,
        role_slug: str,
        jd_url: Optional[str],
    ) -> ScrapingResult:
        """Try Jina Reader → Greenhouse API → BeautifulSoup in order."""

        # ── Tier 1: Jina Reader ──────────────────────────────────────────────
        if jd_url:
            result = await cls._fetch_jina(
                company_name=company_name,
                company_slug=company_slug,
                role_title=role_title,
                role_slug=role_slug,
                jd_url=jd_url,
            )
            if result:
                return result

        # ── Tier 2: Greenhouse API ───────────────────────────────────────────
        greenhouse_slug = GREENHOUSE_BOARDS.get(company_slug)
        if greenhouse_slug:
            result = await cls._fetch_greenhouse(
                company_name=company_name,
                company_slug=company_slug,
                greenhouse_slug=greenhouse_slug,
                role_title=role_title,
                role_slug=role_slug,
            )
            if result:
                return result

        # ── Tier 3: BeautifulSoup fallback on JD URL ─────────────────────────
        if jd_url:
            result = await cls._fetch_beautifulsoup(
                company_name=company_name,
                company_slug=company_slug,
                role_title=role_title,
                role_slug=role_slug,
                jd_url=jd_url,
            )
            if result:
                return result

        # ── Final: Empty scaffold ────────────────────────────────────────────
        logger.warning(f"All JD fetch tiers failed for {company_name} / {role_title}")
        return ScrapingResult(
            company_slug=company_slug,
            role_slug=role_slug,
            company_name=company_name,
            role_title=role_title,
            raw_jd_text="",
            required_skills=[],
            nice_to_have_skills=[],
            jd_url=jd_url,
            source="failed",
        )

    @classmethod
    async def _fetch_jina(
        cls,
        company_name: str,
        company_slug: str,
        role_title: str,
        role_slug: str,
        jd_url: str,
    ) -> Optional[ScrapingResult]:
        """Fetch via Jina Reader r.jina.ai/<url> for clean Markdown text."""
        jina_url = f"{cls.JINA_BASE}{jd_url}"
        try:
            async with httpx.AsyncClient(timeout=cls.REQUEST_TIMEOUT) as client:
                headers = {
                    "Accept": "text/plain",
                    "X-Return-Format": "text",
                }
                try:
                    from app.core.config import settings
                    jina_key = getattr(settings, "JINA_API_KEY", "")
                    if jina_key:
                        headers["Authorization"] = f"Bearer {jina_key}"
                except Exception:
                    pass

                resp = await client.get(jina_url, headers=headers)
                resp.raise_for_status()
                raw_text = resp.text.strip()
                if len(raw_text) < 100:
                    return None

            required, nice_to_have = _extract_skills_from_jd_text(raw_text)
            return ScrapingResult(
                company_slug=company_slug,
                role_slug=role_slug,
                company_name=company_name,
                role_title=role_title,
                raw_jd_text=raw_text[:8000],
                required_skills=required,
                nice_to_have_skills=nice_to_have,
                jd_url=jd_url,
                source="jina_reader",
                scraped_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.debug(f"Jina Reader fetch failed for {jd_url}: {exc}")
            return None

    @classmethod
    async def _fetch_greenhouse(
        cls,
        company_name: str,
        company_slug: str,
        greenhouse_slug: str,
        role_title: str,
        role_slug: str,
    ) -> Optional[ScrapingResult]:
        """Fetch from Greenhouse public JSON API and find best-matching job."""
        url = f"{cls.GREENHOUSE_BASE}/{greenhouse_slug}/jobs"
        try:
            async with httpx.AsyncClient(timeout=cls.REQUEST_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            jobs = data.get("jobs", [])
            if not jobs:
                return None

            # Find closest matching role by title
            role_lower = role_title.lower()
            best_job = None
            best_score = 0
            for job in jobs:
                title = (job.get("title") or "").lower()
                words_overlap = len(set(role_lower.split()) & set(title.split()))
                if words_overlap > best_score:
                    best_score = words_overlap
                    best_job = job

            if not best_job or best_score == 0:
                return None

            # Fetch full job detail
            job_id = best_job.get("id")
            detail_url = f"{cls.GREENHOUSE_BASE}/{greenhouse_slug}/jobs/{job_id}"
            async with httpx.AsyncClient(timeout=cls.REQUEST_TIMEOUT) as client:
                detail_resp = await client.get(detail_url)
                detail_resp.raise_for_status()
                detail = detail_resp.json()

            raw_html = detail.get("content", "") or ""
            soup = BeautifulSoup(raw_html, "html.parser")
            raw_text = soup.get_text(separator="\n").strip()

            required, nice_to_have = _extract_skills_from_jd_text(raw_text)
            return ScrapingResult(
                company_slug=company_slug,
                role_slug=role_slug,
                company_name=company_name,
                role_title=best_job.get("title", role_title),
                raw_jd_text=raw_text[:8000],
                required_skills=required,
                nice_to_have_skills=nice_to_have,
                jd_url=detail.get("absolute_url"),
                source="greenhouse",
                scraped_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.debug(f"Greenhouse fetch failed for {greenhouse_slug}: {exc}")
            return None

    @classmethod
    async def _fetch_beautifulsoup(
        cls,
        company_name: str,
        company_slug: str,
        role_title: str,
        role_slug: str,
        jd_url: str,
    ) -> Optional[ScrapingResult]:
        """Fallback: direct HTTP fetch + BeautifulSoup HTML parsing."""
        try:
            async with httpx.AsyncClient(
                timeout=cls.REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Interviewer-Bot/1.0)"},
            ) as client:
                resp = await client.get(jd_url)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            raw_text = soup.get_text(separator="\n").strip()
            if len(raw_text) < 50:
                return None

            required, nice_to_have = _extract_skills_from_jd_text(raw_text)
            return ScrapingResult(
                company_slug=company_slug,
                role_slug=role_slug,
                company_name=company_name,
                role_title=role_title,
                raw_jd_text=raw_text[:8000],
                required_skills=required,
                nice_to_have_skills=nice_to_have,
                jd_url=jd_url,
                source="beautifulsoup",
                scraped_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.debug(f"BeautifulSoup fetch failed for {jd_url}: {exc}")
            return None
