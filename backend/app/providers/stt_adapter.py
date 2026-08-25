"""Phase 10D: Normalized Real Speech-to-Text Provider Adapter.

Implements STTProvider with response normalization, latency tracking,
input audio validation, and conservative retry policies.
"""

import time
import asyncio
import io
from typing import Optional, Dict, Any
import httpx

from app.ai.base import STTProvider
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


class RealSTTAdapter(STTProvider):
    """Cloud Speech-to-Text adapter (e.g. OpenAI Whisper / compatible cloud endpoints)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[ProviderConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.config = config or provider_config
        self.api_key = api_key or self.config.OPENAI_API_KEY
        self.model = model or self.config.OPENAI_STT_MODEL
        self._custom_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.STT_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav"
    ) -> Dict[str, Any]:
        """
        Transcribes audio bytes into normalized transcription result dictionary.
        """
        ProviderValidator.validate_stt_input(
            audio_bytes=audio_bytes,
            filename=filename,
            max_bytes=self.config.MAX_STT_AUDIO_BYTES
        )

        if not self.api_key or not self.api_key.strip():
            raise ProviderAuthenticationError(
                "OPENAI_API_KEY is not configured for STT provider.",
                provider="whisper"
            )

        endpoint = f"{self.config.OPENAI_BASE_URL.rstrip('/')}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}"
        }

        start_time = time.monotonic()
        last_error: Optional[Exception] = None
        client = self._get_client()

        for attempt in range(1, self.config.MAX_RETRIES + 1):
            try:
                # Prepare multipart upload
                files = {
                    "file": (filename, io.BytesIO(audio_bytes), "audio/wav"),
                    "model": (None, self.model)
                }

                response = await client.post(endpoint, headers=headers, files=files)
                latency_ms = (time.monotonic() - start_time) * 1000.0

                if response.status_code == 200:
                    data = response.json()
                    transcript_text = data.get("text", "").strip()

                    normalized_result = {
                        "text": transcript_text,
                        "language": data.get("language", "en"),
                        "confidence": float(data.get("confidence", 0.95)),
                        "duration_ms": round(latency_ms, 2),
                        "is_final": True,
                        "provider": "whisper",
                        "model": self.model
                    }

                    usage_tracker.record_usage(
                        provider="whisper",
                        operation="stt",
                        model=self.model,
                        characters=len(transcript_text),
                        audio_bytes=len(audio_bytes),
                        latency_ms=latency_ms,
                        success=True
                    )

                    return normalized_result

                if response.status_code in (401, 403):
                    raise ProviderAuthenticationError(
                        f"STT provider authentication failed (HTTP {response.status_code}). Check API key.",
                        provider="whisper"
                    )

                if response.status_code == 429:
                    raise ProviderRateLimitError(
                        "STT provider rate limit exceeded (HTTP 429).",
                        provider="whisper"
                    )

                if response.status_code == 400:
                    raise ProviderValidationError(
                        f"STT provider rejected audio (HTTP 400): {response.text[:200]}",
                        provider="whisper"
                    )

                if response.status_code >= 500:
                    last_error = ProviderUnavailableError(
                        f"STT provider service unavailable (HTTP {response.status_code}).",
                        provider="whisper",
                        status_code=response.status_code
                    )

            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                last_error = ProviderTimeoutError(
                    f"STT request timed out after {self.config.STT_TIMEOUT_SECONDS}s.",
                    provider="whisper",
                    raw_error=e
                )
            except (httpx.NetworkError, httpx.ConnectError) as e:
                last_error = ProviderNetworkError(
                    f"STT provider network error: {str(e)}",
                    provider="whisper",
                    raw_error=e
                )
            except (ProviderAuthenticationError, ProviderRateLimitError, ProviderValidationError):
                raise

            if attempt < self.config.MAX_RETRIES:
                delay = self.config.INITIAL_BACKOFF_SEC * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        total_latency_ms = (time.monotonic() - start_time) * 1000.0
        usage_tracker.record_usage(
            provider="whisper",
            operation="stt",
            model=self.model,
            characters=0,
            audio_bytes=len(audio_bytes),
            latency_ms=total_latency_ms,
            success=False,
            error_type=type(last_error).__name__ if last_error else "UnknownError"
        )

        if last_error:
            raise last_error
        raise ProviderUnavailableError("STT request failed after retries.", provider="whisper")
