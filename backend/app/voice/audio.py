"""Phase 10A: Audio Validation & Metadata Extraction.

Validates audio payloads, inspects magic headers, enforces size and duration constraints,
and extracts structured metadata.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from app.voice.exceptions import (
    AudioValidationError,
    UnsupportedAudioFormatError,
    AudioTooLargeError,
    AudioDurationError,
)
from app.voice.security import (
    VoiceSecurity,
    MAX_AUDIO_SIZE_BYTES,
    MIN_AUDIO_SIZE_BYTES,
)

# Supported audio format extensions and MIME types
SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "webm", "m4a", "flac"}
SUPPORTED_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/ogg", "audio/vorbis",
    "audio/webm",
    "audio/mp4", "audio/x-m4a", "audio/m4a",
    "audio/flac", "audio/x-flac"
}


@dataclass(frozen=True)
class AudioMetadata:
    """Immutable metadata descriptor for validated audio."""
    filename: str
    format: str
    mime_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "format": self.format,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "is_valid": self.is_valid
        }


class AudioValidator:
    """Production audio payload validator with fail-closed magic byte inspection."""

    @staticmethod
    def inspect_magic_format(audio_bytes: bytes) -> Optional[str]:
        """
        Inspect the binary header to detect legitimate audio formats.
        Returns format extension ('wav', 'mp3', etc.) or None if unknown.
        """
        if len(audio_bytes) < 4:
            return None

        # 1. WAV / RIFF
        if audio_bytes.startswith(b"RIFF") and len(audio_bytes) >= 12 and audio_bytes[8:12] == b"WAVE":
            return "wav"

        # 2. MP3 (ID3 tag or frame sync header 0xFFFB, 0xFFFA, 0xFFF3, 0xFFF2)
        if audio_bytes.startswith(b"ID3") or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0):
            return "mp3"

        # 3. OGG
        if audio_bytes.startswith(b"OggS"):
            return "ogg"

        # 4. WebM / Matroska EBML
        if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            return "webm"

        # 5. FLAC
        if audio_bytes.startswith(b"fLaC"):
            return "flac"

        # 6. M4A / MP4 (ftyp box at offset 4)
        if len(audio_bytes) >= 8 and audio_bytes[4:8] == b"ftyp":
            return "m4a"

        return None

    @staticmethod
    def validate_audio(
        audio_bytes: Optional[bytes],
        filename: Optional[str] = "audio.wav",
        mime_type: Optional[str] = None,
        max_size_bytes: int = MAX_AUDIO_SIZE_BYTES,
        max_duration_seconds: float = 300.0,
        expected_duration_seconds: Optional[float] = None
    ) -> AudioMetadata:
        """
        Comprehensive audio validation.
        Validates:
        - Non-null, non-empty payload
        - Min/max byte boundaries
        - Filename safety (path traversal prevention)
        - Extension and MIME format conformance
        - Magic byte integrity
        - Duration limits (if provided or extractable)
        """
        # 1. Null / Empty Checks
        if audio_bytes is None:
            raise AudioValidationError("Audio bytes payload cannot be None.")
        
        size = len(audio_bytes)
        if size == 0:
            raise AudioValidationError("Audio payload is empty (0 bytes).")

        # 2. Size boundaries
        if size < MIN_AUDIO_SIZE_BYTES:
            raise AudioValidationError(f"Audio payload is too small ({size} bytes). Must contain at least valid audio header.")

        if size > max_size_bytes:
            raise AudioTooLargeError(f"Audio payload size ({size} bytes) exceeds maximum limit ({max_size_bytes} bytes).")

        # 3. Safe Filename
        safe_filename = VoiceSecurity.sanitize_filename(filename)
        ext = Path(safe_filename).suffix.lstrip(".").lower()

        # 4. Magic Header Format Inspection
        detected_format = AudioValidator.inspect_magic_format(audio_bytes)
        if not detected_format:
            raise UnsupportedAudioFormatError("Malformed or unrecognized audio binary header.")

        # Conformance between file extension and detected binary format
        effective_format = detected_format
        if ext and ext in SUPPORTED_FORMATS:
            if ext != detected_format and not (ext in ("mp4", "m4a") and detected_format == "m4a"):
                raise UnsupportedAudioFormatError(f"Extension '{ext}' does not match detected format '{detected_format}'.")

        # 5. MIME Type verification if provided
        effective_mime = mime_type or f"audio/{effective_format}"
        if mime_type:
            clean_mime = mime_type.lower().split(";")[0].strip()
            if clean_mime not in SUPPORTED_MIME_TYPES:
                raise UnsupportedAudioFormatError(f"MIME type '{clean_mime}' is not supported.")

        # 6. Duration bounds
        duration = expected_duration_seconds
        if duration is not None:
            if duration <= 0:
                raise AudioDurationError(f"Audio duration must be greater than 0 seconds (got {duration}).")
            if duration > max_duration_seconds:
                raise AudioDurationError(f"Audio duration ({duration}s) exceeds maximum allowed ({max_duration_seconds}s).")

        return AudioMetadata(
            filename=safe_filename,
            format=effective_format,
            mime_type=effective_mime,
            size_bytes=size,
            duration_seconds=duration,
            is_valid=True
        )
