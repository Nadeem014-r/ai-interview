"""Phase 10B: Object Storage Abstraction & Sandboxed Local Storage.

Provides a unified object storage interface for session artifacts and recordings
with strict path traversal protection.
"""

import os
import re
from pathlib import Path
from typing import Optional, Protocol

from app.realtime.config import config
from app.realtime.exceptions import StorageError


class StorageService(Protocol):
    """Protocol for object storage backends."""
    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        ...

    async def get_object(self, key: str) -> Optional[bytes]:
        ...

    async def delete_object(self, key: str) -> bool:
        ...

    async def exists(self, key: str) -> bool:
        ...


class LocalStorage:
    """Production-grade local file system storage with path traversal sandboxing."""

    def __init__(self, base_path: Optional[str] = None, max_bytes: int = config.STORAGE_MAX_OBJECT_BYTES):
        self.base_path = Path(base_path or config.STORAGE_PATH).resolve()
        self.max_bytes = max_bytes
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, key: str) -> Path:
        """
        Resolves object key inside sandbox directory.
        Raises StorageError if path traversal or illegal characters are detected.
        """
        if not key or not key.strip():
            raise StorageError("Storage key cannot be empty.")

        clean_key = key.strip()
        if "\0" in clean_key or ".." in clean_key:
            raise StorageError(f"Path traversal detected in storage key: '{key}'.")

        # Resolve relative to base_path
        target_path = (self.base_path / clean_key.lstrip("/\\")).resolve()

        # Enforce sandbox containment
        try:
            target_path.relative_to(self.base_path)
        except ValueError as e:
            raise StorageError(f"Storage path escaped sandbox directory: '{key}'.", raw_error=e)

        return target_path

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store an object under the given key."""
        if data is None:
            raise StorageError("Object data cannot be None.")

        if len(data) > self.max_bytes:
            raise StorageError(f"Object size ({len(data)}B) exceeds maximum storage limit ({self.max_bytes}B).")

        path = self._resolve_safe_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return str(path)
        except Exception as e:
            raise StorageError(f"Failed to write object '{key}': {str(e)}", raw_error=e)

    async def get_object(self, key: str) -> Optional[bytes]:
        """Retrieve stored object bytes."""
        path = self._resolve_safe_path(key)
        if not path.is_file():
            return None
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            raise StorageError(f"Failed to read object '{key}': {str(e)}", raw_error=e)

    async def delete_object(self, key: str) -> bool:
        """Delete an object if it exists."""
        path = self._resolve_safe_path(key)
        if path.is_file():
            try:
                path.unlink()
                return True
            except Exception as e:
                raise StorageError(f"Failed to delete object '{key}': {str(e)}", raw_error=e)
        return False

    async def exists(self, key: str) -> bool:
        """Check if object exists."""
        try:
            path = self._resolve_safe_path(key)
            return path.is_file()
        except StorageError:
            return False
