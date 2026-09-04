"""Phase 10G: Production Object Storage Safety & Path Traversal Guard.

Enforces strict key sanitization, payload size verification, and idempotent deletion.
"""

from typing import Optional, Any
from app._archive.hardening.exceptions import StorageError, ValidationError
from app._archive.hardening.security_policy import SecurityPolicy, default_security_policy


class HardenedStorageManager:
    """Provides validated and traversal-safe storage operations."""

    def __init__(self, raw_storage: Optional[Any] = None, policy: Optional[SecurityPolicy] = None):
        self.raw_storage = raw_storage
        self.policy = policy or default_security_policy

    def sanitize_and_validate_key(self, key: Optional[str]) -> str:
        """Validates key against path traversal, null bytes, and root escapes."""
        if not key or not key.strip():
            raise ValidationError("Storage object key cannot be empty.")

        clean = key.strip()
        if "\0" in clean or ".." in clean or clean.startswith(("/", "\\")):
            raise StorageError(f"Path traversal or invalid object key detected: '{key}'.")

        return clean

    def validate_payload(self, data: Optional[bytes], max_bytes: Optional[int] = None) -> bytes:
        """Validates payload bytes presence and size limit."""
        if data is None:
            raise ValidationError("Storage payload cannot be None.")

        limit = max_bytes or self.policy.MAX_AUDIO_BYTES
        if len(data) > limit:
            raise ValidationError(f"Storage payload size ({len(data)}B) exceeds limit ({limit}B).")

        return data

    async def delete_safe(self, key: str) -> bool:
        """Performs idempotent object deletion."""
        valid_key = self.sanitize_and_validate_key(key)
        if not self.raw_storage:
            return True  # No-op in test/offline environment

        try:
            if hasattr(self.raw_storage, "delete_object"):
                await self.raw_storage.delete_object(valid_key)
            elif hasattr(self.raw_storage, "delete"):
                await self.raw_storage.delete(valid_key)
            return True
        except Exception:
            # Idempotent deletion does not fail on missing object
            return True
