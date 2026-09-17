import asyncio
import hashlib
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup, NavigableString

from app.core.config import settings
from app.research.security import (
    URLSecurityValidator,
    ResearchSecurityError,
    InvalidURLError,
    SSRFProtectionError,
    DisallowedDomainError
)

logger = logging.getLogger("ai_interviewer.research.crawler")

# Short standalone headings that open a job-description section. Generic across
# careers sites; used to locate the JD region of a page that also carries job
# lists, navigation and other unrelated sections.
_JD_SECTION_HEADING = re.compile(
    r"(?:(?:minimum|preferred|basic|required|key|additional|desired)\s+)?"
    r"(?:qualifications|requirements|responsibilities|skills(?:\s+and\s+experience)?)"
    r"|about\s+(?:the|this)\s+(?:job|role|position|team|opportunity)"
    r"|job\s+description|role\s+overview|what\s+you(?:'|’)?ll\s+do|what\s+you\s+will\s+do"
    r"|who\s+you\s+are|what\s+we(?:'|’)?re\s+looking\s+for|nice\s+to\s+have"
    r"|tech(?:nology|nical)?\s+stack|technologies",
    re.IGNORECASE,
)

# Lines carrying legal/EEO/cookie boilerplate rather than role information.
_BOILERPLATE_LINE = re.compile(
    r"equal\s+opportunity|affirmative\s+action|all\s+rights\s+reserved|cookie"
    r"|privacy\s+(?:policy|notice)|terms\s+of\s+(?:service|use)|agency\s+resumes"
    r"|unsolicited\s+resumes|reasonable\s+accommodation|accommodations?\s+for\s+applicants",
    re.IGNORECASE,
)

# Short page-control lines (share/apply buttons, icon ligature names) left behind
# when a site renders controls as links or spans rather than <button>.
_UI_CONTROL_LINE = re.compile(
    r"(?:[a-z]+_)*[a-z]+_[a-z]+|apply(?:\s+now)?|share\b.*|.*copy\s+link|.*email\s+a\s+friend"
    r"|save(?:\s+job)?|back\s+to\s+.*|sign\s+in|log\s+in",
    re.IGNORECASE,
)

# Chrome whose markup identifies it as navigation, banners, dialogs or consent UI.
_NOISE_ROLES = {"navigation", "banner", "contentinfo", "dialog", "alertdialog", "search"}
_NOISE_ATTR = re.compile(r"cookie|consent|gdpr", re.IGNORECASE)

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
        for tag in soup.find_all(cls._is_noise_container):
            if not tag.decomposed:
                tag.decompose()

        # 3. Extract text preserving block separations
        # Source-formatting line breaks inside a text node are not content breaks;
        # collapsing them keeps a wrapped <p> as one line instead of fragments.
        for text_node in soup.find_all(string=True):
            if type(text_node) is NavigableString and ("\n" in text_node or "\r" in text_node):
                text_node.replace_with(re.sub(r"\s+", " ", str(text_node)))
        # Add newlines for block elements
        for block in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "div", "section", "article"]):
            block.insert(0, "\n")
            block.append("\n")

        # Narrow to the job-description region when the page clearly has one, so
        # job lists and other sections sharing the page are not indexed with it.
        raw_text = cls._find_jd_region(soup).get_text()

        # 4. Normalize whitespace and drop legal/cookie boilerplate lines
        lines = []
        for line in raw_text.split("\n"):
            cleaned_line = " ".join(line.split())
            if not cleaned_line or _BOILERPLATE_LINE.search(cleaned_line):
                continue
            if len(cleaned_line.split()) <= 6 and _UI_CONTROL_LINE.fullmatch(cleaned_line):
                continue
            lines.append(cleaned_line)

        cleaned_text = "\n".join(lines).strip()
        return title, cleaned_text

    @staticmethod
    def _is_noise_container(tag) -> bool:
        """Elements marked up as navigation/banner/dialog chrome or cookie-consent UI."""
        if tag.attrs is None:
            return False
        if (tag.get("role") or "").lower() in _NOISE_ROLES:
            return True
        marker = " ".join([tag.get("id") or "", " ".join(tag.get("class") or [])])
        return bool(marker.strip()) and bool(_NOISE_ATTR.search(marker))

    @staticmethod
    def _find_jd_region(soup):
        """Return the smallest element containing every job-description section heading.

        Requires at least two distinct headings (e.g. "Responsibilities" and
        "Minimum qualifications") and a substantial amount of text; otherwise the
        whole document is returned, which is the previous behaviour.
        """
        headings = []
        for text_node in soup.find_all(string=True):
            text = " ".join(str(text_node).split()).rstrip(":").strip()
            if text and len(text) <= 60 and _JD_SECTION_HEADING.fullmatch(text) and text_node.parent is not None:
                headings.append((text.lower(), text_node.parent))
        if len({label for label, _ in headings}) < 2:
            return soup

        def ancestors(node):
            chain = []
            while node is not None:
                chain.append(node)
                node = node.parent
            return chain

        common = ancestors(headings[0][1])
        for _, element in headings[1:]:
            chain_ids = {id(n) for n in ancestors(element)}
            common = [n for n in common if id(n) in chain_ids]
        region = common[0] if common else soup
        if len(region.get_text(" ").split()) < 40:
            return soup
        return region

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
