"""Phase 10C: Security Request & Input Validation Utilities.

Protects against path traversal, oversized uploads, and malicious file names.
"""

import re
from pathlib import Path
from typing import Set, Optional

from app.production.exceptions import SecurityConfigurationError, StorageValidationError


class SecurityValidator:
    """Production input & boundary validator."""

    @staticmethod
    def validate_filename(filename: Optional[str]) -> str:
        """
        Validates and sanitizes a user-supplied filename.
        Rejects directory traversal sequences and dangerous characters.
        """
        if not filename or not filename.strip():
            raise StorageValidationError("Filename cannot be empty.")

        clean = filename.strip()
        if "\0" in clean or ".." in clean or "/" in clean or "\\" in clean:
            raise StorageValidationError(f"Path traversal or illegal character detected in filename: '{filename}'.")

        sanitized = Path(clean).name
        sanitized = re.sub(r'[^A-Za-z0-9_.-]', '_', sanitized)
        if not sanitized or sanitized.startswith("."):
            raise StorageValidationError("Invalid sanitized filename.")

        return sanitized

    @staticmethod
    def validate_payload_size(size_bytes: int, max_bytes: int, entity_name: str = "Payload") -> None:
        """Enforces payload byte limits."""
        if size_bytes > max_bytes:
            raise StorageValidationError(f"{entity_name} size ({size_bytes}B) exceeds maximum allowable limit ({max_bytes}B).")

    @staticmethod
    def validate_content_type(content_type: str, allowed_types: Set[str]) -> bool:
        """Verifies content-type against an allowed set."""
        clean = content_type.lower().split(";")[0].strip()
        return clean in allowed_types
