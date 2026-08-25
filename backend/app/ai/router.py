"""Phase 8: Model & Provider Router.

Routes AI requests to the configured primary provider with deterministic fallback
handling, rate limit failover, and offline safety.
"""

import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.ai.base import LLMProvider, EmbeddingProvider
from app.ai.exceptions import (
    AIError,
    AIAuthenticationError,
    AIFallbackExhaustedError,
    AIProviderError,
)

logger = logging.getLogger("ai_interviewer.ai.router")


class RoutedLLMProvider(LLMProvider):
    """LLM Provider wrapper that handles primary provider routing and automatic fallback."""

    def __init__(
        self,
        primary_provider: LLMProvider,
        fallback_provider: Optional[LLMProvider] = None,
        enable_fallback: bool = True
    ):
        self.primary = primary_provider
        self.fallback = fallback_provider
        self.enable_fallback = enable_fallback

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        try:
            return await self.primary.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )
        except Exception as primary_err:
            if not self.enable_fallback or self.fallback is None:
                raise primary_err

            logger.warning(
                f"Primary LLM provider failed ({primary_err}). Triggering fallback provider...",
                exc_info=False
            )
            try:
                return await self.fallback.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    **kwargs
                )
            except Exception as fallback_err:
                logger.error(f"Fallback LLM provider also failed: {fallback_err}", exc_info=True)
                raise AIFallbackExhaustedError(
                    f"Both primary ({primary_err}) and fallback ({fallback_err}) failed."
                ) from fallback_err

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
        try:
            return await self.primary.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                **kwargs
            )
        except Exception as primary_err:
            if not self.enable_fallback or self.fallback is None:
                raise primary_err

            logger.warning(
                f"Primary LLM generate_json failed ({primary_err}). Triggering fallback provider...",
                exc_info=False
            )
            try:
                return await self.fallback.generate_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    schema=schema,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    **kwargs
                )
            except Exception as fallback_err:
                logger.error(f"Fallback LLM generate_json also failed: {fallback_err}", exc_info=True)
                raise AIFallbackExhaustedError(
                    f"Both primary ({primary_err}) and fallback ({fallback_err}) failed for structured JSON."
                ) from fallback_err


class RoutedEmbeddingProvider(EmbeddingProvider):
    """Embedding Provider wrapper that handles primary provider routing and automatic fallback."""

    def __init__(
        self,
        primary_provider: EmbeddingProvider,
        fallback_provider: Optional[EmbeddingProvider] = None,
        enable_fallback: bool = True
    ):
        self.primary = primary_provider
        self.fallback = fallback_provider
        self.enable_fallback = enable_fallback

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        try:
            return await self.primary.embed_text(text, model=model)
        except Exception as primary_err:
            if not self.enable_fallback or self.fallback is None:
                raise primary_err

            logger.warning(f"Primary embedding failed ({primary_err}). Falling back...", exc_info=False)
            try:
                return await self.fallback.embed_text(text, model=model)
            except Exception as fallback_err:
                raise AIFallbackExhaustedError(
                    f"Both primary ({primary_err}) and fallback ({fallback_err}) embeddings failed."
                ) from fallback_err

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        try:
            return await self.primary.embed_batch(texts, model=model)
        except Exception as primary_err:
            if not self.enable_fallback or self.fallback is None:
                raise primary_err

            logger.warning(f"Primary batch embedding failed ({primary_err}). Falling back...", exc_info=False)
            try:
                return await self.fallback.embed_batch(texts, model=model)
            except Exception as fallback_err:
                raise AIFallbackExhaustedError(
                    f"Both primary ({primary_err}) and fallback ({fallback_err}) batch embeddings failed."
                ) from fallback_err
