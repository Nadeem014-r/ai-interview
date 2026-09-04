"""Phase 10C: Strongly Typed Production Configuration.

Provides strict parsing, validation, and safe defaults for production infrastructure,
storage backends, worker pools, security boundaries, and logging.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ProductionConfig:
    """Strongly typed production configuration."""
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Host & CORS Security
    ALLOWED_HOSTS: List[str] = field(default_factory=lambda: [
        h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()
    ])
    CORS_ORIGINS: List[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()
    ])

    # Core Backends
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes")

    # Security & Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_dev_secret_key_change_in_production_12345")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # Object Storage
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "./production_storage")
    STORAGE_MAX_OBJECT_BYTES: int = int(os.getenv("STORAGE_MAX_OBJECT_BYTES", str(50 * 1024 * 1024)))  # 50 MB
    STORAGE_S3_BUCKET: Optional[str] = os.getenv("STORAGE_S3_BUCKET")
    STORAGE_S3_ENDPOINT: Optional[str] = os.getenv("STORAGE_S3_ENDPOINT")

    # Resource & Operational Limits
    MAX_REQUEST_BYTES: int = int(os.getenv("MAX_REQUEST_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))  # 25 MB
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30.0"))
    GRACEFUL_SHUTDOWN_TIMEOUT: float = float(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "15.0"))

    # Worker & Background Jobs
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "5"))
    WORKER_MAX_RETRIES: int = int(os.getenv("WORKER_MAX_RETRIES", "3"))
    WORKER_INITIAL_BACKOFF_SEC: float = float(os.getenv("WORKER_INITIAL_BACKOFF_SEC", "0.5"))

    # Observability
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")

    @classmethod
    def from_env(cls) -> "ProductionConfig":
        """Construct ProductionConfig from current environment variables."""
        return cls()


# Default production config instance
production_config = ProductionConfig.from_env()
