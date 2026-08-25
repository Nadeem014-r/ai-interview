"""Phase 10D: Production-Grade ElevenLabs Text-to-Speech Adapter.

Implements the TTSProvider interface with async HTTP connection reuse,
conservative exponential retries, strict validation, and monotonic latency measurement.
"""

import time
import asyncio
import logging
from typing import Optional, Tuple, Dict, Any
import httpx

from app.ai.base import TTSProvider
from app.providers.config import provider_config, ProviderConfig
from app.providers.validation import ProviderValidator
from app.providers.usage import usage_tracker
from app.providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderNetworkError,
    ProviderUnavailableError,
    ProviderResponseError,
    ProviderValidationError,
)

logger = logging.getLogger("app.providers.elevenlabs")


class ElevenLabsTTSProvider(TTSProvider):
    """Production ElevenLabs Text-to-Speech provider adapter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[ProviderConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.config = config or provider_config
        self.api_key = api_key or self.config.ELEVENLABS_API_KEY
        self.default_voice_id = voice_id or self.config.ELEVENLABS_VOICE_ID
        self.model = model or self.config.ELEVENLABS_MODEL
        self._custom_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.ELEVENLABS_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        """
        Synthesizes text into audio bytes using ElevenLabs API.
        Preserves standard TTSProvider signature.
        """
        audio_bytes, _ = await self.synthesize_speech_with_metadata(text, voice_id=voice_id)
        return audio_bytes

    async def synthesize_speech_with_metadata(
        self,
        text: str,
        voice_id: str = "default"
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Synthesizes text into speech audio bytes and returns structured operation metadata.
        """
        resolved_voice_id = self.default_voice_id if voice_id == "default" else voice_id
        ProviderValidator.validate_tts_input(
            text=text,
            voice_id=resolved_voice_id,
            max_chars=self.config.MAX_TTS_TEXT_CHARS
        )

        if not self.api_key or not self.api_key.strip():
            raise ProviderAuthenticationError(
                "ELEVENLABS_API_KEY is not configured or is empty.",
                provider="elevenlabs"
            )

        endpoint = f"{self.config.ELEVENLABS_BASE_URL.rstrip('/')}/text-to-speech/{resolved_voice_id}"
        headers = {
            "xi-api-key": self.api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        start_time = time.monotonic()
        last_error: Optional[Exception] = None
        client = self._get_client()

        for attempt in range(1, self.config.MAX_RETRIES + 1):
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    params={"output_format": self.config.ELEVENLABS_OUTPUT_FORMAT}
                )

                latency_ms = (time.monotonic() - start_time) * 1000.0

                # 1. Successful synthesis
                if response.status_code == 200:
                    audio_bytes = response.content
                    if not audio_bytes or len(audio_bytes) == 0:
                        raise ProviderResponseError("ElevenLabs returned empty audio payload.", provider="elevenlabs")

                    metadata = {
                        "provider": "elevenlabs",
                        "model": self.model,
                        "voice_id": resolved_voice_id,
                        "audio_bytes_length": len(audio_bytes),
                        "characters": len(text),
                        "latency_ms": round(latency_ms, 2),
                        "success": True
                    }

                    usage_tracker.record_usage(
                        provider="elevenlabs",
                        operation="tts",
                        model=self.model,
                        voice=resolved_voice_id,
                        characters=len(text),
                        audio_bytes=len(audio_bytes),
                        latency_ms=latency_ms,
                        success=True
                    )

                    return audio_bytes, metadata

                # 2. Permanent non-retryable errors
                if response.status_code in (401, 403):
                    raise ProviderAuthenticationError(
                        f"ElevenLabs authentication failed (HTTP {response.status_code}). Check ELEVENLABS_API_KEY.",
                        provider="elevenlabs"
                    )

                if response.status_code == 429:
                    retry_after = float(response.headers.get("retry-after", 5.0))
                    raise ProviderRateLimitError(
                        f"ElevenLabs rate limit exceeded (HTTP 429). Retry after {retry_after}s.",
                        provider="elevenlabs",
                        retry_after=retry_after
                    )

                if response.status_code == 400:
                    raise ProviderValidationError(
                        f"ElevenLabs rejected payload (HTTP 400): {response.text[:200]}",
                        provider="elevenlabs"
                    )

                # 3. Retryable server errors (5xx)
                if response.status_code >= 500:
                    last_error = ProviderUnavailableError(
                        f"ElevenLabs service unavailable (HTTP {response.status_code}).",
                        provider="elevenlabs",
                        status_code=response.status_code
                    )

            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                last_error = ProviderTimeoutError(
                    f"ElevenLabs request timed out after {self.config.ELEVENLABS_TIMEOUT_SECONDS}s.",
                    provider="elevenlabs",
                    raw_error=e
                )
            except (httpx.NetworkError, httpx.ConnectError) as e:
                last_error = ProviderNetworkError(
                    f"ElevenLabs network connection failed: {str(e)}",
                    provider="elevenlabs",
                    raw_error=e
                )
            except (ProviderAuthenticationError, ProviderRateLimitError, ProviderValidationError):
                # Never retry client / authentication errors
                raise

            # Retry delay for transient errors
            if attempt < self.config.MAX_RETRIES:
                delay = self.config.INITIAL_BACKOFF_SEC * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        # Retries exhausted
        total_latency_ms = (time.monotonic() - start_time) * 1000.0
        usage_tracker.record_usage(
            provider="elevenlabs",
            operation="tts",
            model=self.model,
            voice=resolved_voice_id,
            characters=len(text),
            audio_bytes=0,
            latency_ms=total_latency_ms,
            success=False,
            error_type=type(last_error).__name__ if last_error else "UnknownError"
        )

        if last_error:
            raise last_error
        raise ProviderUnavailableError("ElevenLabs request failed after retries.", provider="elevenlabs")
