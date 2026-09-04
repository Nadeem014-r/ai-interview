"""Phase 10H: Operational Backup Abstraction & Verification.

Provides structured backup metadata generation, integrity verification, and retention policy management.
"""

import time
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class BackupMetadata:
    backup_id: str
    target_type: str  # database, storage_meta, config
    created_at: float = field(default_factory=time.time)
    size_bytes: int = 0
    checksum_sha256: str = ""
    status: str = "created"  # created, verified, archived, deleted


class BackupManager:
    """Manages backup manifests, checksum verifications, and retention pruning."""

    def __init__(self, retention_days: int = 30):
        self.retention_days = retention_days
        self._backups: Dict[str, BackupMetadata] = {}

    def register_backup(
        self,
        backup_id: str,
        target_type: str,
        data_payload: bytes
    ) -> BackupMetadata:
        """Registers and fingerprints a new backup artifact."""
        sha = hashlib.sha256(data_payload).hexdigest()
        meta = BackupMetadata(
            backup_id=backup_id,
            target_type=target_type,
            size_bytes=len(data_payload),
            checksum_sha256=sha,
            status="created"
        )
        self._backups[backup_id] = meta
        return meta

    def verify_backup(self, backup_id: str, data_payload: bytes) -> bool:
        """Verifies backup payload integrity against registered SHA256 checksum."""
        meta = self._backups.get(backup_id)
        if not meta:
            return False

        computed_sha = hashlib.sha256(data_payload).hexdigest()
        if computed_sha == meta.checksum_sha256:
            meta.status = "verified"
            return True
        else:
            meta.status = "corrupted"
            return False

    def prune_expired_backups(self, current_time: Optional[float] = None) -> List[str]:
        """Identifies and marks backups older than retention_days."""
        now = current_time or time.time()
        retention_seconds = self.retention_days * 86400.0
        pruned = []

        for b_id, meta in list(self._backups.items()):
            if (now - meta.created_at) > retention_seconds:
                meta.status = "deleted"
                pruned.append(b_id)

        return pruned
