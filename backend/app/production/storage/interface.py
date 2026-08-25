"""Phase 10C: Production Storage Service Protocol.
"""

from typing import Protocol, Optional, List


class ProductionStorageService(Protocol):
    """Abstract interface for production object storage."""

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store binary payload under key."""
        ...

    async def get_object(self, key: str) -> Optional[bytes]:
        """Retrieve binary payload."""
        ...

    async def delete_object(self, key: str) -> bool:
        """Delete stored object."""
        ...

    async def exists(self, key: str) -> bool:
        """Check object existence."""
        ...

    async def list_objects(self, prefix: str = "") -> List[str]:
        """List object keys matching prefix."""
        ...
