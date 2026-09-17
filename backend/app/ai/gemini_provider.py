"""Phase 8: Production-Grade Gemini AI Provider.

Integrates with Google Gemini models (Gemini 3.6 Flash, Gemini 1.5 Pro, Text-Embedding-004)
with resilience retries, structured JSON schema validation, token tracking, and embedding safety.
"""

import asyncio
import time
import httpx
from typing import List, Dict, Any, Optional
from app.ai.base import LLMProvider, EmbeddingProvider
from app.core.config import settings
from app.ai.exceptions import (
    AIAuthenticationError,
    AIInvalidRequestError,
    AIStructuredOutputError,
    AIEmbeddingError,
)
from app.ai.resilience import execute_with_resilience
from app.ai.json_parser import extract_and_parse_json
from app.ai.schemas import validate_structured_data
from app.ai.observability import log_ai_operation
from app.ai.token_counter import estimate_tokens


# A new AsyncClient per request meant a fresh TCP connect and TLS handshake on
# every LLM call. On an interview turn that cost is paid three times over while
# the candidate waits in silence, and a slow handshake was enough to push a call
# past its timeout and into the retry path. Clients are cached per event loop
# because an httpx client is bound to the loop that created it -- one global
# client would break under pytest, which runs each test in its own loop.
_HTTP_CLIENTS: "Dict[Any, httpx.AsyncClient]" = {}


def _get_shared_client(timeout: float) -> httpx.AsyncClient:
    """Return a connection-pooled client for the running event loop."""
    loop = asyncio.get_running_loop()
    client = _HTTP_CLIENTS.get(loop)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
        )
        _HTTP_CLIENTS[loop] = client
    return client


class GeminiLLMProvider(LLMProvider):
    """Google Gemini LLM provider implementation."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = settings.GEMINI_API_KEY if api_key is None else api_key
        self.default_model = default_model or settings.GEMINI_DEFAULT_MODEL or "gemini-3.6-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        if not self.api_key:
            raise AIAuthenticationError("GEMINI_API_KEY is not set or empty.", provider="gemini")

        target_model = model or self.default_model
        url = f"{self.base_url}/{target_model}:generateContent"

        # 512 was too small for a full evaluation rubric: the JSON was cut off
        # mid-object, parsing failed, and the turn silently degraded to canned
        # output. Reasoning-capable models also bill thought tokens against this
        # budget, so the ceiling must clear the response by a wide margin.
        effective_max_tokens = max_tokens or settings.LLM_MAX_OUTPUT_TOKENS or 2048
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": effective_max_tokens,
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        start_time = time.time()
        timeout = kwargs.get("timeout", settings.LLM_REQUEST_TIMEOUT_SECONDS)

        async def _call() -> str:
            client = _get_shared_client(timeout)
            res = await client.post(
                url, json=payload, headers={"x-goog-api-key": self.api_key}, timeout=timeout
            )
            res.raise_for_status()
            data = res.json()


            candidates = data.get("candidates")
            if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
                prompt_feedback = data.get("promptFeedback", {})
                block_reason = prompt_feedback.get("blockReason", "Unknown block reason")
                raise AIInvalidRequestError(f"Gemini API returned no candidates. Block reason: {block_reason}", provider="gemini")

            first_candidate = candidates[0]
            content = first_candidate.get("content")
            if not content or not isinstance(content, dict):
                finish_reason = first_candidate.get("finishReason", "UNKNOWN")
                raise AIInvalidRequestError(f"Gemini returned empty content with finishReason: {finish_reason}", provider="gemini")

            parts = content.get("parts")
            if not parts or not isinstance(parts, list) or len(parts) == 0:
                finish_reason = first_candidate.get("finishReason", "UNKNOWN")
                raise AIInvalidRequestError(f"Gemini returned empty parts list with finishReason: {finish_reason}", provider="gemini")

            text_part = parts[0].get("text")
            if text_part is None:
                raise AIInvalidRequestError(f"Missing text field in Gemini candidate part: {parts[0]}", provider="gemini")

            return text_part

        try:
            result_text = await execute_with_resilience(_call, provider="gemini", operation_name="generate_text")
            latency_ms = int((time.time() - start_time) * 1000)
            in_tokens = estimate_tokens(prompt) + (estimate_tokens(system_prompt) if system_prompt else 0)
            out_tokens = estimate_tokens(result_text)
            log_ai_operation("generate_text", "gemini", target_model, latency_ms, in_tokens, out_tokens, success=True)
            return result_text
        except Exception as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            log_ai_operation("generate_text", "gemini", target_model, latency_ms, success=False, error=str(exc))
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        json_sys_prompt = f"{system_prompt or ''}\nOutput strictly valid JSON only. Do not include markdown commentary outside the JSON."
        
        # Initial attempt
        raw_text = await self.generate_text(
            prompt=prompt,
            system_prompt=json_sys_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            **kwargs
        )
        
        try:
            parsed = extract_and_parse_json(raw_text, provider="gemini")
            if schema:
                return validate_structured_data(parsed, schema, provider="gemini")
            return parsed if isinstance(parsed, dict) else {"items": parsed}
        except AIStructuredOutputError as parse_err:
            # Single bounded retry for malformed or schema-invalid JSON
            retry_prompt = f"{prompt}\n\nPREVIOUS RESPONSE WAS INVALID JSON OR FAILED SCHEMA:\n{parse_err.message}\nPlease return valid JSON."
            raw_retry_text = await self.generate_text(
                prompt=retry_prompt,
                system_prompt=json_sys_prompt,
                temperature=0.1,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )
            parsed_retry = extract_and_parse_json(raw_retry_text, provider="gemini")
            if schema:
                return validate_structured_data(parsed_retry, schema, provider="gemini")
            return parsed_retry if isinstance(parsed_retry, dict) else {"items": parsed_retry}


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider (gemini-embedding-001)."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = settings.GEMINI_API_KEY if api_key is None else api_key
        self.default_model = default_model or settings.GEMINI_EMBEDDING_MODEL or "gemini-embedding-001"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        if not self.api_key:
            raise AIAuthenticationError("GEMINI_API_KEY is not set or empty.", provider="gemini")
        if text is None:
            text = ""

        target_model = model or self.default_model
        url = f"{self.base_url}/{target_model}:embedContent"
        payload = {
            "model": f"models/{target_model}",
            "content": {"parts": [{"text": text}]}
        }

        async def _call() -> List[float]:
            client = _get_shared_client(15.0)
            res = await client.post(
                url, json=payload, headers={"x-goog-api-key": self.api_key}, timeout=15.0
            )
            res.raise_for_status()
            data = res.json()
            try:
                values = data["embedding"]["values"]
                if not isinstance(values, list) or len(values) == 0:
                    raise AIEmbeddingError("Empty embedding vector returned from Gemini.", provider="gemini")
                return [float(x) for x in values]
            except (KeyError, TypeError) as e:
                raise AIEmbeddingError(f"Malformed embedding response from Gemini: {data}", provider="gemini") from e

        return await execute_with_resilience(_call, provider="gemini", operation_name="embed_text")

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        if not texts:
            return []
        
        # Gemini batch embed sequentially or with bounded concurrency
        results = []
        for text in texts:
            results.append(await self.embed_text(text, model=model))
        return results
