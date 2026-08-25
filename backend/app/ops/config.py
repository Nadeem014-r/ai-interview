"""Phase 10F: Production Operations Configuration Layer.

Provides typed, environment-driven settings, safe defaults, and secret-safe export.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

from app.ops.secrets import redact_secrets


@dataclass(frozen=True)
class ProductionOpsConfig:
    """Strongly typed production operational configuration."""

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Security & Networking
    SECRET_KEY: str = os.getenv("SECRET_KEY", "insecure_dev_secret_key_change_in_production_12345")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    ALLOWED_HOSTS: List[str] = field(default_factory=lambda: [
        h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
    ])
    CORS_ORIGINS: List[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()
    ])

    # Databases & Caching
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes")

    # Storage & File Limits
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "./production_storage")
    MAX_REQUEST_BYTES: int = int(os.getenv("MAX_REQUEST_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))    # 25 MB

    # Operational & Worker Timeouts
    WORKER_COUNT: int = int(os.getenv("WORKER_COUNT", "4"))
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30.0"))
    GRACEFUL_SHUTDOWN_TIMEOUT: float = float(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "15.0"))
    HEALTH_CACHE_SECONDS: float = float(os.getenv("HEALTH_CACHE_SECONDS", "5.0"))

    # Observability
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @classmethod
    def from_env(cls) -> "ProductionOpsConfig":
        return cls()

    def to_safe_dict(self) -> Dict[str, Any]:
        """Returns configuration dictionary with all secrets recursively redacted."""
        raw = {
            "ENVIRONMENT": self.ENVIRONMENT,
            "DEBUG": self.DEBUG,
            "SECRET_KEY": self.SECRET_KEY,
            "JWT_ALGORITHM": self.JWT_ALGORITHM,
            "ACCESS_TOKEN_EXPIRE_MINUTES": self.ACCESS_TOKEN_EXPIRE_MINUTES,
            "ALLOWED_HOSTS": self.ALLOWED_HOSTS,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "DATABASE_URL": self.DATABASE_URL,
            "REDIS_URL": self.REDIS_URL,
            "USE_REDIS": self.USE_REDIS,
            "STORAGE_LOCAL_PATH": self.STORAGE_LOCAL_PATH,
            "MAX_REQUEST_BYTES": self.MAX_REQUEST_BYTES,
            "MAX_UPLOAD_BYTES": self.MAX_UPLOAD_BYTES,
            "WORKER_COUNT": self.WORKER_COUNT,
            "REQUEST_TIMEOUT_SECONDS": self.REQUEST_TIMEOUT_SECONDS,
            "GRACEFUL_SHUTDOWN_TIMEOUT": self.GRACEFUL_SHUTDOWN_TIMEOUT,
            "LOG_LEVEL": self.LOG_LEVEL
        }
        return redact_secrets(raw)


ops_config = ProductionOpsConfig.from_env()
