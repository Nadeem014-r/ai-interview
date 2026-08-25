"""Phase 8: Resilience, Retry Handling, and Error Normalization.

Provides exponential backoff with jitter, Retry-After header parsing,
and translation of raw HTTP/provider errors into normalized AI exceptions.
"""

import asyncio
import logging
import random
import re
from typing import Callable, Any, Optional, Dict
import httpx

from app.core.config import settings
from app.ai.exceptions import (
    AIError,
    AIProviderError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIInvalidRequestError,
    AIModelNotFoundError,
)

logger = logging.getLogger("ai_interviewer.ai.resilience")

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
PERMANENT_STATUS_CODES = {400, 401, 403, 404, 422}


def parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse Retry-After header value in seconds or return None."""
    if not header_value:
        return None
    try:
        val = float(header_value.strip())
        return min(max(0.1, val), 60.0)  # Bound between 100ms and 60s
    except ValueError:
        return None


def normalize_http_status_error(
    exc: httpx.HTTPStatusError,
    provider: str
) -> AIError:
    """Translate raw httpx.HTTPStatusError into a normalized AI exception."""
    status_code = exc.response.status_code
    response_text = exc.response.text

    if status_code in (401, 403):
        return AIAuthenticationError(
            f"Authentication failed for provider '{provider}'. Check API key.",
            provider=provider,
            raw_error=response_text
        )
    elif status_code == 404:
        return AIModelNotFoundError(
            f"Model or endpoint not found on provider '{provider}': {response_text}",
            provider=provider,
            raw_error=response_text
        )
    elif status_code == 429:
        retry_after = parse_retry_after(exc.response.headers.get("Retry-After"))
        return AIRateLimitError(
            f"Rate limit or quota exceeded for provider '{provider}'.",
            provider=provider,
            raw_error=response_text,
            retry_after=retry_after
        )
    elif status_code == 400 or status_code == 422:
        return AIInvalidRequestError(
            f"Invalid request sent to provider '{provider}': {response_text}",
            provider=provider,
            raw_error=response_text
        )
    else:
        return AIProviderError(
            f"Provider '{provider}' returned HTTP {status_code}: {response_text}",
            provider=provider,
            raw_error=response_text
        )


async def execute_with_resilience(
    coro_func: Callable[[], Any],
    provider: str,
    max_retries: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    operation_name: str = "ai_request"
) -> Any:
    """
    Execute an async AI request function with bounded retries and exponential backoff.
    Permanent errors (401, 403, 400, 404) are raised immediately without retrying.
    Transient errors (429, 500, 502, 503, 504, network drops, timeouts) are retried.
    """
    retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
    backoff = backoff_factor if backoff_factor is not None else settings.LLM_RETRY_BACKOFF_FACTOR

    attempt = 0
    while True:
        try:
            return await coro_func()
        except httpx.TimeoutException as exc:
            attempt += 1
            if attempt > retries:
                logger.error(f"[{provider}] Operation '{operation_name}' timed out after {attempt} attempts: {exc}")
                raise AITimeoutError(f"Request to provider '{provider}' timed out after {attempt} attempts.", provider=provider, raw_error=exc) from exc
            
            sleep_time = (backoff * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
            logger.warning(f"[{provider}] Timeout on attempt {attempt}/{retries} for '{operation_name}'. Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)

        except httpx.NetworkError as exc:
            attempt += 1
            if attempt > retries:
                logger.error(f"[{provider}] Network error after {attempt} attempts: {exc}")
                raise AIProviderError(f"Network failure connecting to provider '{provider}'.", provider=provider, raw_error=exc) from exc
            
            sleep_time = (backoff * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
            logger.warning(f"[{provider}] Network error on attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in PERMANENT_STATUS_CODES:
                # Do NOT retry permanent errors
                normalized_err = normalize_http_status_error(exc, provider)
                logger.error(f"[{provider}] Non-retryable HTTP {status_code} error: {normalized_err.message}")
                raise normalized_err from exc

            # Transient HTTP errors (429, 5xx)
            attempt += 1
            if attempt > retries:
                normalized_err = normalize_http_status_error(exc, provider)
                logger.error(f"[{provider}] Exhausted {retries} retries for HTTP {status_code}: {normalized_err.message}")
                raise normalized_err from exc

            # Determine sleep time (respect Retry-After if present)
            retry_after_hdr = parse_retry_after(exc.response.headers.get("Retry-After"))
            if retry_after_hdr is not None:
                sleep_time = retry_after_hdr
            else:
                sleep_time = (backoff * (2 ** (attempt - 1))) + random.uniform(0, 0.1)

            logger.warning(f"[{provider}] Transient HTTP {status_code} on attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)

        except AIError:
            # Re-raise normalized AI errors directly
            raise

        except Exception as exc:
            # Unexpected failure
            attempt += 1
            if attempt > retries:
                logger.error(f"[{provider}] Unexpected error after {attempt} attempts: {exc}", exc_info=True)
                raise AIProviderError(f"Unexpected provider error: {exc}", provider=provider, raw_error=exc) from exc
            
            sleep_time = (backoff * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
            await asyncio.sleep(sleep_time)
