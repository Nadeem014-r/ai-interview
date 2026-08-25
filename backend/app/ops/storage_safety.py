"""Phase 10F: Object Storage Production Safety & Path Traversal Protection.

Validates object keys, payload sizes, and content types before storage access.
"""

from typing import Set, Optional
from app.ops.config import ops_config
from app.ops.exceptions import OpsStorageError, OpsValidationError
from app.production.security.validation import SecurityValidator


class StorageSafetySupervisor:
    """Production validator for object storage boundaries."""

    ALLOWED_AUDIO_TYPES: Set[str] = {"audio/wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/ogg"}
    ALLOWED_DOCUMENT_TYPES: Set[str] = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

    @staticmethod
    def validate_storage_key(key: Optional[str]) -> str:
        """Enforces path traversal safety on object keys."""
        if not key or not key.strip():
            raise OpsValidationError("Storage key cannot be empty.")

        clean = key.strip()
        if "\0" in clean or ".." in clean:
            raise OpsStorageError(f"Path traversal detected in key: '{key}'.")

        return clean.lstrip("/\\")

    @staticmethod
    def validate_object_bytes(data: Optional[bytes], max_bytes: int = ops_config.MAX_UPLOAD_BYTES) -> None:
        """Validates payload size bounds."""
        if data is None:
            raise OpsValidationError("Object data payload cannot be None.")

        if len(data) > max_bytes:
            raise OpsValidationError(f"Payload size ({len(data)}B) exceeds limit ({max_bytes}B).")

    @staticmethod
    def validate_content_type(content_type: str, allowed_types: Optional[Set[str]] = None) -> bool:
        """Validates content-type against allowable MIME types."""
        allowed = allowed_types or (StorageSafetySupervisor.ALLOWED_AUDIO_TYPES | StorageSafetySupervisor.ALLOWED_DOCUMENT_TYPES)
        clean = content_type.lower().split(";")[0].strip()
        return clean in allowed
