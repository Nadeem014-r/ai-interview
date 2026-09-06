"""Phase 8: Production AI Provider Factory.

Instantiates and configures LLM, Embedding, STT, and TTS providers with
model routing, automatic fallback, and backward-compatible interfaces.
"""

import logging
from typing import Optional
from app.core.config import settings
from app.ai.base import LLMProvider, EmbeddingProvider, STTProvider, TTSProvider
from app.ai.mock_provider import MockLLMProvider, MockEmbeddingProvider, MockSTTProvider, MockTTSProvider
from app.ai.gemini_provider import GeminiLLMProvider, GeminiEmbeddingProvider
from app.ai.openai_provider import OpenAILLMProvider, OpenAIEmbeddingProvider
from app.ai.router import RoutedLLMProvider, RoutedEmbeddingProvider
from app.ai.exceptions import AIAuthenticationError, AIProviderError

logger = logging.getLogger("ai_interviewer.ai_factory")

PRODUCTION_ENVIRONMENTS = {"production", "prod"}


def _implicit_mock_allowed() -> bool:
    """Whether a mock may stand in for a provider the operator actually asked for.

    Substituting a mock is a development convenience -- it keeps the platform
    usable offline. In production the same substitution serves fabricated output
    as a genuine result: a mock rubric scored as though the model produced it, or
    a canned transcript recorded as the candidate's own spoken answer. Callers
    cannot tell the difference, because the substitution happens below them and
    the request still succeeds.

    So implicit substitution is refused in production and the real failure is
    raised instead, leaving each caller's own deterministic degraded path (for
    example AnswerEvaluator's fallback rubric) to handle it honestly.

    Selecting "mock" explicitly in configuration is always honoured; only the
    implicit swap is gated.
    """
    return (settings.ENVIRONMENT or "").strip().lower() not in PRODUCTION_ENVIRONMENTS


class AIFactory:
    """Unified Factory for AI Providers."""

    @staticmethod
    def _create_raw_llm_provider(provider_name: str) -> LLMProvider:
        """Create a direct LLM provider instance without fallback wrapper."""
        p_name = provider_name.lower().strip()
        if p_name == "gemini":
            return GeminiLLMProvider()
        elif p_name == "openai":
            return OpenAILLMProvider()
        elif p_name == "mock":
            return MockLLMProvider()
        else:
            logger.warning(f"Unknown LLM provider '{provider_name}'. Defaulting to MockLLMProvider.")
            return MockLLMProvider()

    @staticmethod
    def _create_raw_embedding_provider(provider_name: str) -> EmbeddingProvider:
        """Create a direct Embedding provider instance without fallback wrapper."""
        p_name = provider_name.lower().strip()
        if p_name == "gemini":
            return GeminiEmbeddingProvider()
        elif p_name == "openai":
            return OpenAIEmbeddingProvider()
        elif p_name == "mock":
            return MockEmbeddingProvider()
        else:
            logger.warning(f"Unknown Embedding provider '{provider_name}'. Defaulting to MockEmbeddingProvider.")
            return MockEmbeddingProvider()

    @staticmethod
    def get_llm_provider(
        provider_name: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
        fallback_name: Optional[str] = None
    ) -> LLMProvider:
        """
        Get an LLM provider.
        If provider is not explicitly set, reads DEFAULT_LLM_PROVIDER.
        Wraps with fallback provider (defaults to mock) if fallback is enabled.
        """
        primary_name = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()

        use_fallback = enable_fallback if enable_fallback is not None else settings.LLM_ENABLE_FALLBACK
        fb_name = (fallback_name or settings.LLM_FALLBACK_PROVIDER).lower()

        # If primary has no API key and is not mock, auto-fallback to mock immediately
        missing = None
        if primary_name == "gemini" and not settings.GEMINI_API_KEY:
            missing = ("gemini", "GEMINI_API_KEY")
        elif primary_name == "openai" and not settings.OPENAI_API_KEY:
            missing = ("openai", "OPENAI_API_KEY")
        if missing:
            provider, key_name = missing
            if not _implicit_mock_allowed():
                raise AIAuthenticationError(
                    f"{key_name} is not configured, so LLM provider '{provider}' cannot be used. "
                    "Refusing to substitute mock output in production.",
                    provider=provider,
                )
            logger.info(f"{key_name} not set. Using MockLLMProvider (offline mode).")
            return MockLLMProvider()

        primary_inst = AIFactory._create_raw_llm_provider(primary_name)
        if not use_fallback or isinstance(primary_inst, MockLLMProvider) or primary_name == fb_name:
            return primary_inst

        fallback_inst = AIFactory._create_raw_llm_provider(fb_name)
        if isinstance(fallback_inst, MockLLMProvider) and not _implicit_mock_allowed():
            # A mock fallback would turn a real provider outage into a fabricated
            # success. Leave the primary unwrapped so the failure reaches the caller.
            logger.warning(
                f"LLM_FALLBACK_PROVIDER is '{fb_name}'; not wiring a mock fallback in production. "
                f"A '{primary_name}' failure will surface as an error."
            )
            return primary_inst
        return RoutedLLMProvider(
            primary_provider=primary_inst,
            fallback_provider=fallback_inst,
            enable_fallback=True
        )

    @staticmethod
    def get_embedding_provider(
        provider_name: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
        fallback_name: Optional[str] = None
    ) -> EmbeddingProvider:
        """
        Get an Embedding provider.
        If provider is not explicitly set, reads DEFAULT_EMBEDDING_PROVIDER.
        Wraps with fallback provider if enabled.
        """
        primary_name = (provider_name or settings.DEFAULT_EMBEDDING_PROVIDER).lower()
        use_fallback = enable_fallback if enable_fallback is not None else settings.LLM_ENABLE_FALLBACK
        fb_name = (fallback_name or settings.LLM_FALLBACK_PROVIDER).lower()

        missing = None
        if primary_name == "gemini" and not settings.GEMINI_API_KEY:
            missing = ("gemini", "GEMINI_API_KEY")
        elif primary_name == "openai" and not settings.OPENAI_API_KEY:
            missing = ("openai", "OPENAI_API_KEY")
        if missing:
            provider, key_name = missing
            if not _implicit_mock_allowed():
                raise AIAuthenticationError(
                    f"{key_name} is not configured, so embedding provider '{provider}' cannot be used. "
                    "Refusing to substitute mock embeddings in production.",
                    provider=provider,
                )
            logger.info(f"{key_name} not set. Using MockEmbeddingProvider (offline mode).")
            return MockEmbeddingProvider()

        primary_inst = AIFactory._create_raw_embedding_provider(primary_name)
        if not use_fallback or isinstance(primary_inst, MockEmbeddingProvider) or primary_name == fb_name:
            return primary_inst

        fallback_inst = AIFactory._create_raw_embedding_provider(fb_name)
        if isinstance(fallback_inst, MockEmbeddingProvider) and not _implicit_mock_allowed():
            # Mock embeddings would silently make retrieval meaningless while
            # every RAG call still reported success.
            logger.warning(
                f"LLM_FALLBACK_PROVIDER is '{fb_name}'; not wiring a mock embedding fallback in production."
            )
            return primary_inst
        return RoutedEmbeddingProvider(
            primary_provider=primary_inst,
            fallback_provider=fallback_inst,
            enable_fallback=True
        )

    @staticmethod
    def _stt_unavailable(reason: str) -> STTProvider:
        """Mock STT returns a canned transcript, which would be stored and scored
        as the candidate's own spoken answer. Never substitute it in production."""
        if not _implicit_mock_allowed():
            raise AIProviderError(
                f"Speech-to-text is unavailable: {reason}. Refusing to substitute a "
                "fabricated transcript in production.",
                provider="stt",
            )
        logger.warning(f"{reason}. Falling back to MockSTTProvider.")
        return MockSTTProvider()

    @staticmethod
    def get_stt_provider(provider_name: Optional[str] = None) -> STTProvider:
        """Get Speech-to-Text provider."""
        from app.providers.config import provider_config
        p_name = (provider_name or getattr(settings, "DEFAULT_STT_PROVIDER", None) or provider_config.DEFAULT_STT_PROVIDER or "whisper").lower().strip()
        if p_name == "mock":
            return MockSTTProvider()
        if p_name in ("whisper", "whisper_small", "whisper_stt", "local_whisper"):
            try:
                from app.providers.whisper_stt import WhisperSmallSTTProvider
                return WhisperSmallSTTProvider()
            except Exception as e:
                return AIFactory._stt_unavailable(f"Failed to instantiate WhisperSmallSTTProvider: {e}")
        elif p_name in ("openai", "openai_whisper"):
            api_key = getattr(settings, "OPENAI_API_KEY", None) or provider_config.OPENAI_API_KEY
            if api_key and str(api_key).strip():
                try:
                    from app.providers.stt_adapter import RealSTTAdapter
                    return RealSTTAdapter()
                except Exception as e:
                    return AIFactory._stt_unavailable(f"Failed to instantiate RealSTTAdapter: {e}")
            else:
                logger.info("OPENAI_API_KEY not set. Using WhisperSmallSTTProvider (local mode).")
                try:
                    from app.providers.whisper_stt import WhisperSmallSTTProvider
                    return WhisperSmallSTTProvider()
                except Exception as e:
                    return AIFactory._stt_unavailable(f"Failed to instantiate WhisperSmallSTTProvider: {e}")
        return AIFactory._stt_unavailable(f"unknown STT provider '{p_name}'")

    @staticmethod
    def _tts_unavailable(reason: str) -> TTSProvider:
        """Mock TTS emits a 440 Hz tone. Serving that as the interviewer's voice
        while reporting success hides an outage, so production raises instead."""
        if not _implicit_mock_allowed():
            raise AIProviderError(
                f"Text-to-speech is unavailable: {reason}. Refusing to substitute "
                "simulated audio in production.",
                provider="tts",
            )
        logger.warning(f"{reason}. Falling back to MockTTSProvider.")
        return MockTTSProvider()

    @staticmethod
    def get_tts_provider(
        provider_name: Optional[str] = None,
        enable_fallback: Optional[bool] = None
    ) -> TTSProvider:
        """Get Text-to-Speech provider with Kokoro 0.9.4 integration and safe fallback."""
        from app.providers.config import provider_config
        p_name = (provider_name or getattr(settings, "DEFAULT_TTS_PROVIDER", None) or provider_config.DEFAULT_TTS_PROVIDER or "kokoro").lower().strip()
        # A mock fallback behind a real engine turns an outage into a fabricated
        # success, so in production the engine is used unwrapped.
        use_fallback = (
            enable_fallback if enable_fallback is not None else True
        ) and _implicit_mock_allowed()
        fallback_inst = MockTTSProvider()

        if p_name in ("kokoro", "kokoro_tts", "local_kokoro"):
            try:
                from app.providers.kokoro_tts import KokoroTTSProvider
                primary_inst = KokoroTTSProvider()
                if use_fallback:
                    from app.ai.router import RoutedTTSProvider
                    return RoutedTTSProvider(
                        primary_provider=primary_inst,
                        fallback_provider=fallback_inst,
                        enable_fallback=True
                    )
                return primary_inst
            except Exception as e:
                return AIFactory._tts_unavailable(f"Failed to instantiate KokoroTTSProvider: {e}")
        elif p_name == "elevenlabs":
            api_key = getattr(settings, "ELEVENLABS_API_KEY", None) or provider_config.ELEVENLABS_API_KEY
            if api_key and str(api_key).strip():
                try:
                    from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
                    primary_inst = ElevenLabsTTSProvider()
                    if use_fallback:
                        from app.ai.router import RoutedTTSProvider
                        return RoutedTTSProvider(
                            primary_provider=primary_inst,
                            fallback_provider=fallback_inst,
                            enable_fallback=True
                        )
                    return primary_inst
                except Exception as e:
                    return AIFactory._tts_unavailable(f"Failed to instantiate ElevenLabsTTSProvider: {e}")
            else:
                logger.info("ELEVENLABS_API_KEY not configured. Falling back to KokoroTTSProvider.")
                try:
                    from app.providers.kokoro_tts import KokoroTTSProvider
                    return KokoroTTSProvider()
                except Exception as e:
                    return AIFactory._tts_unavailable(f"Failed to instantiate KokoroTTSProvider: {e}")
        elif p_name == "mock":
            return fallback_inst
        return AIFactory._tts_unavailable(f"unknown TTS provider '{p_name}'")

