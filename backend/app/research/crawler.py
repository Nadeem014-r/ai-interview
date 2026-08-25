import asyncio
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.research.security import (
    URLSecurityValidator,
    ResearchSecurityError,
    InvalidURLError,
    SSRFProtectionError,
    DisallowedDomainError
)

logger = logging.getLogger("ai_interviewer.research.crawler")

class CrawlerError(Exception):
    """Base exception for crawler failures."""
    pass

class UnsupportedContentTypeError(CrawlerError):
    """Raised when the fetched resource is not HTML or plain text."""
    pass

class OversizedContentError(CrawlerError):
    """Raised when the remote resource exceeds max response size limit."""
    pass

class EmptyContentError(CrawlerError):
    """Raised when the remote resource contains no meaningful readable text."""
    pass

class FetchTimeoutError(CrawlerError):
    """Raised when the request times out."""
    pass

class HTTPFetchError(CrawlerError):
    """Raised for non-transient or unrecoverable HTTP status codes."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code

class PlaywrightUnavailableError(CrawlerError):
    """Raised when Playwright is required but not installed or enabled."""
    pass

class CompanyResearchCrawler:
    MAX_REDIRECTS = 5
    ALLOWED_CONTENT_TYPES = {
        "text/html",
        "text/plain",
        "application/xhtml+xml"
    }

    @classmethod
    def clean_html_content(cls, raw_html: str) -> Tuple[str, str]:
        """
        Extract meaningful title and clean text from raw HTML using BeautifulSoup.
        Removes scripts, styles, navigation, footer, forms, and excessive whitespace.
        Returns: (title, cleaned_text)
        """
        if not raw_html or not raw_html.strip():
            return "", ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        # 2. Strip noise tags
        noise_tags = [
            "script", "style", "noscript", "nav", "header", "footer",
            "svg", "form", "iframe", "button", "aside"
        ]
        for tag in soup.find_all(noise_tags):
            tag.decompose()

        # 3. Extract text preserving block separations
        # Add newlines for block elements
        for block in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "div", "section", "article"]):
            block.append("\n")

        raw_text = soup.get_text()

        # 4. Normalize whitespace
        lines = []
        for line in raw_text.split("\n"):
            cleaned_line = " ".join(line.split())
            if cleaned_line:
                lines.append(cleaned_line)

        cleaned_text = "\n".join(lines).strip()
        return title, cleaned_text

    @classmethod
    def compute_content_hash(cls, text: str) -> str:
        """Compute deterministic SHA-256 hash of normalized text."""
        normalized = text.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    async def _fetch_with_playwright(cls, url: str, allowed_domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Controlled JavaScript-rendered fetch using Playwright if enabled and installed.
        """
        if not settings.RESEARCH_ENABLE_PLAYWRIGHT:
            raise PlaywrightUnavailableError("Playwright rendering is disabled in settings.")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise PlaywrightUnavailableError("Playwright is not installed in the environment.")

        logger.info(f"Using Playwright JS rendering for {url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                
                # SSRF guard on page requests
                async def route_handler(route):
                    req_url = route.request.url
                    try:
                        URLSecurityValidator.validate_url(req_url, allowed_domains)
                        await route.continue_()
                    except ResearchSecurityError:
                        await route.abort()

                await page.route("**/*", route_handler)
                await page.goto(url, timeout=int(settings.RESEARCH_REQUEST_TIMEOUT_SECONDS * 1000), wait_until="networkidle")
                
                content = await page.content()
                title, cleaned_text = cls.clean_html_content(content)
                if not cleaned_text or len(cleaned_text) < 15:
                    raise EmptyContentError(f"Page at {url} yielded no readable text even with Playwright.")

                content_hash = cls.compute_content_hash(cleaned_text)
                return {
                    "url": url,
                    "title": title or url,
                    "raw_html": content,
                    "cleaned_text": cleaned_text,
                    "content_hash": content_hash,
                    "status": "success",
                    "extraction_method": "playwright_js"
                }
            finally:
                await browser.close()

    @classmethod
    async def fetch_page_content(
        cls,
        url: str,
        allowed_domains: Optional[List[str]] = None,
        custom_client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously and securely fetch, validate, and clean page content.
        Enforces SSRF protection, domain allowlist, content-type checking, max size limits,
        bounded retries, SHA-256 hashing, and zero fake content fabrication.
        """
        # 1. Validate initial URL
        validated_url = URLSecurityValidator.validate_url(url, allowed_domains)
        current_url = validated_url
        logger.info(f"Starting research fetch for URL: {current_url}")

        timeout = httpx.Timeout(
            timeout=settings.RESEARCH_REQUEST_TIMEOUT_SECONDS,
            connect=min(5.0, settings.RESEARCH_REQUEST_TIMEOUT_SECONDS)
        )
        headers = {
            "User-Agent": settings.RESEARCH_USER_AGENT,
            "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.8"
        }

        # 2. HTTP Fetch with manual redirect validation & transient retry handling
        last_error = None
        for attempt in range(settings.RESEARCH_MAX_RETRIES + 1):
            try:
                # Use provided client or instantiate managed client
                if custom_client is not None:
                    response, final_url = await cls._execute_request_with_redirects(
                        custom_client, current_url, headers, timeout, allowed_domains
                    )
                else:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response, final_url = await cls._execute_request_with_redirects(
                            client, current_url, headers, timeout, allowed_domains
                        )

                # Check HTTP Status Code
                if response.status_code == 200:
                    # Validate Content-Type
                    content_type = response.headers.get("content-type", "").lower()
                    media_type = content_type.split(";")[0].strip()
                    if media_type and media_type not in cls.ALLOWED_CONTENT_TYPES:
                        raise UnsupportedContentTypeError(
                            f"Unsupported Content-Type '{content_type}'. Only HTML and plain text are supported."
                        )

                    # Validate Content Size
                    body_bytes = response.content
                    if len(body_bytes) > settings.RESEARCH_MAX_RESPONSE_SIZE_BYTES:
                        raise OversizedContentError(
                            f"Content size ({len(body_bytes)} bytes) exceeds maximum allowed size ({settings.RESEARCH_MAX_RESPONSE_SIZE_BYTES} bytes)."
                        )

                    raw_text = response.text
                    if not raw_text or not raw_text.strip():
                        raise EmptyContentError(f"Fetched URL {final_url} returned empty content.")

                    # Parse HTML or plain text
                    if "text/plain" in media_type:
                        title = urlparse(final_url).path.split("/")[-1] or final_url
                        cleaned_text = raw_text.strip()
                    else:
                        title, cleaned_text = cls.clean_html_content(raw_text)

                    # Check if extracted text is meaningful
                    if not cleaned_text or len(cleaned_text) < 15:
                        # Attempt Playwright fallback if configured
                        if settings.RESEARCH_ENABLE_PLAYWRIGHT:
                            return await cls._fetch_with_playwright(final_url, allowed_domains)
                        raise EmptyContentError(f"Extracted content from {final_url} contains insufficient text.")

                    content_hash = cls.compute_content_hash(cleaned_text)
                    return {
                        "url": final_url,
                        "title": title or urlparse(final_url).netloc,
                        "raw_html": raw_text,
                        "cleaned_text": cleaned_text,
                        "content_hash": content_hash,
                        "status": "success",
                        "extraction_method": "beautifulsoup4"
                    }

                # Handle transient vs permanent HTTP status codes
                if response.status_code in {502, 503, 504}:
                    raise HTTPFetchError(response.status_code, f"Transient upstream gateway error: {response.status_code}")
                else:
                    # Permanent 4xx / 5xx error
                    raise HTTPFetchError(response.status_code, f"Failed with HTTP status: {response.status_code}")

            except (ResearchSecurityError, UnsupportedContentTypeError, OversizedContentError, EmptyContentError) as non_retryable:
                # Do not retry permanent validation/security errors
                raise non_retryable

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as timeout_err:
                last_error = FetchTimeoutError(f"Request to {current_url} timed out after {settings.RESEARCH_REQUEST_TIMEOUT_SECONDS}s.")
                logger.warning(f"Fetch timeout (attempt {attempt + 1}/{settings.RESEARCH_MAX_RETRIES + 1}): {timeout_err}")

            except (httpx.ConnectError, httpx.NetworkError, HTTPFetchError) as net_err:
                if isinstance(net_err, HTTPFetchError) and net_err.status_code not in {502, 503, 504}:
                    # Non-transient HTTP error, do not retry
                    raise net_err
                last_error = net_err
                logger.warning(f"Transient fetch error (attempt {attempt + 1}/{settings.RESEARCH_MAX_RETRIES + 1}): {net_err}")

            except Exception as unhandled:
                logger.error(f"Unexpected crawler error: {unhandled}", exc_info=True)
                raise CrawlerError(f"Crawler failed unexpectedly: {str(unhandled)}") from unhandled

            # Exponential backoff for transient retries
            if attempt < settings.RESEARCH_MAX_RETRIES:
                backoff = settings.RESEARCH_BACKOFF_FACTOR * (2 ** attempt)
                await asyncio.sleep(backoff)

        # All retries exhausted
        if last_error:
            raise last_error
        raise CrawlerError(f"Failed to fetch content from {url} after {settings.RESEARCH_MAX_RETRIES} retries.")

    @classmethod
    async def _execute_request_with_redirects(
        cls,
        client: httpx.AsyncClient,
        start_url: str,
        headers: Dict[str, str],
        timeout: httpx.Timeout,
        allowed_domains: Optional[List[str]]
    ) -> Tuple[httpx.Response, str]:
        """
        Execute request while explicitly validating every redirect hop against SSRF and domain allowlists.
        """
        current_url = start_url
        redirect_count = 0

        while redirect_count <= cls.MAX_REDIRECTS:
            resp = await client.get(
                current_url,
                headers=headers,
                timeout=timeout,
                follow_redirects=False
            )

            # Check for redirect status codes
            if resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get("Location")
                if not location:
                    return resp, current_url

                # Resolve relative redirects
                next_url = urljoin(current_url, location)
                # STRICT SSRF & DOMAIN VALIDATION ON REDIRECT TARGET
                current_url = URLSecurityValidator.validate_url(next_url, allowed_domains)
                redirect_count += 1
                continue

            return resp, current_url

        raise HTTPFetchError(310, f"Too many redirects (exceeded limit of {cls.MAX_REDIRECTS}).")
