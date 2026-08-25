"""Phase 10A: Voice Security & Boundary Enforcement.

Provides path traversal protection, secret masking, temporary file sandboxing,
and untrusted transcript boundary tagging.
"""

import os
import re
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from app.voice.exceptions import VoiceSecurityError

# Maximum default constraints
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_TTS_TEXT_CHARS = 4000
MIN_AUDIO_SIZE_BYTES = 44  # Minimal valid header size for RIFF WAV


class VoiceSecurity:
    """Security utilities for safe voice and audio processing."""

    @staticmethod
    def sanitize_filename(filename: Optional[str]) -> str:
        """
        Sanitize an audio filename to prevent path traversal.
        Rejects suspicious null bytes, directory traversals, and path separators.
        """
        if not filename or not filename.strip():
            return f"recording_{uuid.uuid4().hex[:8]}.wav"

        raw = filename.strip()
        if "\0" in raw or ".." in raw or "/" in raw or "\\" in raw:
            raise VoiceSecurityError("Path traversal or illegal character detected in filename.")

        # Extract only the base name and strip unsafe characters
        clean = Path(raw).name
        clean = re.sub(r'[^A-Za-z0-9_.-]', '_', clean)
        if not clean or clean.startswith("."):
            return f"recording_{uuid.uuid4().hex[:8]}.wav"
        return clean

    @staticmethod
    def validate_text_length(text: Optional[str], max_chars: int = MAX_TTS_TEXT_CHARS) -> str:
        """Validate that text for TTS synthesis is non-empty and does not exceed max length."""
        if text is None or not text.strip():
            raise VoiceSecurityError("TTS text input cannot be empty.")
        clean = text.strip()
        if len(clean) > max_chars:
            raise VoiceSecurityError(f"TTS text exceeds maximum limit of {max_chars} characters (got {len(clean)}).")
        return clean

    @staticmethod
    def mask_secrets(message: Optional[str]) -> str:
        """Mask API keys and authorization tokens in error messages and logs."""
        if not message:
            return ""
        sanitized = re.sub(r'(?i)bearer\s+([A-Za-z0-9_\-\.]{8,})', 'Bearer [REDACTED_SECRET]', message)
        sanitized = re.sub(r'(?i)(?:key|token|auth|secret)\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{6,})["\']?', '[REDACTED_SECRET]', sanitized)
        sanitized = re.sub(r'(?i)(AIza[0-9A-Za-z-_]{10,})', '[REDACTED_SECRET]', sanitized)
        sanitized = re.sub(r'(?i)(sk-[A-Za-z0-9]{10,})', '[REDACTED_SECRET]', sanitized)
        return sanitized

    @staticmethod
    def create_safe_temp_audio_path(extension: str = ".wav") -> str:
        """Create an isolated, sandboxed temporary file path with a generated UUID filename."""
        temp_dir = tempfile.gettempdir()
        safe_ext = f".{extension.lstrip('.')}"
        filename = f"voice_{uuid.uuid4().hex}{safe_ext}"
        return os.path.join(temp_dir, filename)

    @staticmethod
    def tag_untrusted_transcript(transcript: str) -> str:
        """
        Wrap candidate speech transcript in untrusted data tags so it cannot be
        interpreted as system instructions.
        """
        clean = transcript.strip() if transcript else ""
        return f"<candidate_voice_transcript>\n{clean}\n</candidate_voice_transcript>"
