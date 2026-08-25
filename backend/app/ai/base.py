"""Phase 8: AI Provider Abstractions.

Defines unified abstract base classes for LLMs, Embedding engines, Speech-to-Text,
and Text-to-Speech providers with rich typing, metadata support, and backward compatibility.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    """Encapsulates the response metadata from an LLM call."""
    content: str
    json_data: Optional[Dict[str, Any]] = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    latency_ms: int = 0
    finish_reason: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract interface for LLM text and structured JSON generation."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Generate plain text from prompt."""
        pass

    @abstractmethod
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
        """Generate structured JSON response matching optional schema."""
        pass


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding generation."""

    @abstractmethod
    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate single text embedding vector."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate batch embeddings preserving exact input order."""
        pass


class STTProvider(ABC):
    """Abstract interface for Speech-to-Text transcription."""

    @abstractmethod
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict[str, Any]:
        """Transcribe speech audio to text."""
        pass


class TTSProvider(ABC):
    """Abstract interface for Text-to-Speech synthesis."""

    @abstractmethod
    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        """Synthesize text to speech audio bytes."""
        pass
