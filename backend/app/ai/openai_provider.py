"""Phase 8: Production-Grade OpenAI AI Provider.

Integrates with OpenAI models (GPT-4o, GPT-4o-mini, text-embedding-3-small)
with resilience retries, native batch embeddings, JSON schema validation, and token tracking.
"""

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


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.default_model = default_model or settings.OPENAI_DEFAULT_MODEL or "gpt-4o-mini"
        self.base_url = "https://api.openai.com/v1/chat/completions"

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
            raise AIAuthenticationError("OPENAI_API_KEY is not set or empty.", provider="openai")

        target_model = model or self.default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        start_time = time.time()
        timeout = kwargs.get("timeout", settings.LLM_REQUEST_TIMEOUT_SECONDS)

        async def _call() -> str:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(self.base_url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    raise AIInvalidRequestError(f"Malformed response from OpenAI API: {data}", provider="openai") from e

        try:
            result_text = await execute_with_resilience(_call, provider="openai", operation_name="generate_text")
            latency_ms = int((time.time() - start_time) * 1000)
            in_tokens = estimate_tokens(prompt) + (estimate_tokens(system_prompt) if system_prompt else 0)
            out_tokens = estimate_tokens(result_text)
            log_ai_operation("generate_text", "openai", target_model, latency_ms, in_tokens, out_tokens, success=True)
            return result_text
        except Exception as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            log_ai_operation("generate_text", "openai", target_model, latency_ms, success=False, error=str(exc))
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
        json_sys_prompt = f"{system_prompt or ''}\nOutput strictly valid JSON only."
        raw_text = await self.generate_text(
            prompt=prompt,
            system_prompt=json_sys_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            **kwargs
        )
        try:
            parsed = extract_and_parse_json(raw_text, provider="openai")
            if schema:
                return validate_structured_data(parsed, schema, provider="openai")
            return parsed if isinstance(parsed, dict) else {"items": parsed}
        except AIStructuredOutputError as parse_err:
            retry_prompt = f"{prompt}\n\nPREVIOUS RESPONSE WAS INVALID JSON OR FAILED SCHEMA:\n{parse_err.message}\nPlease return valid JSON."
            raw_retry_text = await self.generate_text(
                prompt=retry_prompt,
                system_prompt=json_sys_prompt,
                temperature=0.1,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )
            parsed_retry = extract_and_parse_json(raw_retry_text, provider="openai")
            if schema:
                return validate_structured_data(parsed_retry, schema, provider="openai")
            return parsed_retry if isinstance(parsed_retry, dict) else {"items": parsed_retry}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider (text-embedding-3-small / text-embedding-3-large)."""

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.default_model = default_model or settings.OPENAI_EMBEDDING_MODEL or "text-embedding-3-small"
        self.base_url = "https://api.openai.com/v1/embeddings"

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        if not self.api_key:
            raise AIAuthenticationError("OPENAI_API_KEY is not set or empty.", provider="openai")
        if text is None:
            text = ""

        target_model = model or self.default_model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"model": target_model, "input": text}

        async def _call() -> List[float]:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(self.base_url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                try:
                    vec = data["data"][0]["embedding"]
                    if not isinstance(vec, list) or len(vec) == 0:
                        raise AIEmbeddingError("Empty embedding vector returned from OpenAI.", provider="openai")
                    return [float(x) for x in vec]
                except (KeyError, IndexError, TypeError) as e:
                    raise AIEmbeddingError(f"Malformed embedding response from OpenAI: {data}", provider="openai") from e

        return await execute_with_resilience(_call, provider="openai", operation_name="embed_text")

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key:
            raise AIAuthenticationError("OPENAI_API_KEY is not set or empty.", provider="openai")

        target_model = model or self.default_model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # OpenAI natively supports a batch array of texts in 'input'
        payload = {"model": target_model, "input": texts}

        async def _call() -> List[List[float]]:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(self.base_url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                try:
                    # Sort by index to strictly guarantee input order preservation
                    items = sorted(data["data"], key=lambda x: x["index"])
                    results = []
                    for item in items:
                        vec = [float(x) for x in item["embedding"]]
                        results.append(vec)
                    return results
                except (KeyError, TypeError, IndexError) as e:
                    raise AIEmbeddingError(f"Malformed batch embedding response from OpenAI: {data}", provider="openai") from e

        return await execute_with_resilience(_call, provider="openai", operation_name="embed_batch")
