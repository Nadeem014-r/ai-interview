"""Phase 10C: Sandboxed Local Object Storage with Atomic Writes.

Implements secure local storage with path traversal protection,
atomic file writes, and size bounds.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, List

from app.production.config import production_config
from app.production.exceptions import ProductionStorageError, StorageValidationError
from app.production.security.validation import SecurityValidator


class ProductionLocalStorage:
    """Production local file system storage with path traversal sandboxing and atomic writes."""

    def __init__(
        self,
        base_path: Optional[str] = None,
        max_bytes: int = production_config.STORAGE_MAX_OBJECT_BYTES
    ):
        self.base_path = Path(base_path or production_config.STORAGE_LOCAL_PATH).resolve()
        self.max_bytes = max_bytes
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        """
        Resolves key within sandbox root.
        Rejects path traversal attacks and null bytes.
        """
        if not key or not key.strip():
            raise StorageValidationError("Storage key cannot be empty.")

        clean_key = key.strip()
        if "\0" in clean_key or ".." in clean_key:
            raise StorageValidationError(f"Path traversal detected in key: '{key}'.")

        # Resolve path
        target = (self.base_path / clean_key.lstrip("/\\")).resolve()

        # Enforce sandbox boundary
        try:
            target.relative_to(self.base_path)
        except ValueError as e:
            raise StorageValidationError(f"Storage path escaped sandbox directory: '{key}'.", raw_error=e)

        return target

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Atomically stores object data under key."""
        if data is None:
            raise StorageValidationError("Object data cannot be None.")

        SecurityValidator.validate_payload_size(len(data), self.max_bytes, "Object")
        path = self._resolve_path(key)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file then rename
            temp_dir = path.parent
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as tmp_file:
                tmp_file.write(data)
                tmp_path = Path(tmp_file.name)

            # Atomic replace
            tmp_path.replace(path)
            return str(path)
        except StorageValidationError:
            raise
        except Exception as e:
            raise ProductionStorageError(f"Failed to store object '{key}': {str(e)}", raw_error=e)

    async def get_object(self, key: str) -> Optional[bytes]:
        """Reads object data."""
        path = self._resolve_path(key)
        if not path.is_file():
            return None
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            raise ProductionStorageError(f"Failed to read object '{key}': {str(e)}", raw_error=e)

    async def delete_object(self, key: str) -> bool:
        """Deletes object if present."""
        path = self._resolve_path(key)
        if path.is_file():
            try:
                path.unlink()
                return True
            except Exception as e:
                raise ProductionStorageError(f"Failed to delete object '{key}': {str(e)}", raw_error=e)
        return False

    async def exists(self, key: str) -> bool:
        """Checks if object exists."""
        try:
            path = self._resolve_path(key)
            return path.is_file()
        except StorageValidationError:
            return False

    async def list_objects(self, prefix: str = "") -> List[str]:
        """Lists object keys relative to sandbox root matching prefix."""
        try:
            keys: List[str] = []
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file():
                    rel = str(file_path.relative_to(self.base_path)).replace("\\", "/")
                    if not prefix or rel.startswith(prefix):
                        keys.append(rel)
            return sorted(keys)
        except Exception as e:
            raise ProductionStorageError(f"Failed to list objects with prefix '{prefix}': {str(e)}", raw_error=e)
