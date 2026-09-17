import os
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum entropy budget for the JWT signing secret (see docs/production.md).
SECRET_KEY_MIN_LENGTH = 32

# Placeholder values that must never be accepted as a real signing secret.
_REJECTED_SECRET_PREFIXES = (
    "change-this",
    "generate_high_entropy",
    "your-secure",
    "default_insecure",
    "production-secret-key",
)


class SecretKeyConfigurationError(RuntimeError):
    """Raised when SECRET_KEY is absent, too short, or a known placeholder.

    Deliberately not a ValueError: pydantic would wrap that in a
    ValidationError whose message embeds the offending input, which prints the
    configured secret (or neighbouring env values) into startup logs.
    """


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    # Secure by default. DEBUG drives SQLAlchemy `echo` (app/core/database.py),
    # which logs every statement *and its bound parameters* -- user emails and
    # password hashes included. docker-compose.yml sets ENVIRONMENT=production
    # but not DEBUG, so a True default leaked that data to container logs.
    DEBUG: bool = False
    APP_NAME: str = "AI Interviewer Platform"
    API_V1_STR: str = "/api/v1"
    # JWT signing secret. Required: must be supplied via the environment (.env or
    # a real env var). The empty default is a non-secret sentinel that the
    # validator below always rejects, so a missing or weak secret fails fast at
    # startup instead of silently signing tokens with a publicly known placeholder.
    SECRET_KEY: str = Field(default="", validate_default=True)
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Comma-separated, like CORS_ORIGINS: pydantic-settings JSON-decodes complex
    # fields from the environment, so a List[str] here rejected the
    # comma-separated form used by .env.example and
    # docker-compose.production.yml (ALLOWED_HOSTS=localhost,127.0.0.1),
    # failing startup with a SettingsError before the app could serve.
    ALLOWED_HOSTS: str = "*"

    # Browser origins allowed to call this API. Credentialed CORS cannot use
    # "*" (browsers reject that combination), so origins are always listed
    # explicitly. Comma-separated in the environment -- the format that
    # .env.example and docker-compose.production.yml already use. The default
    # covers local frontend development only; deployments set CORS_ORIGINS.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_interviewer_db"
    DATABASE_URL: str ="" # Default fallback for zero-dependency dev mode
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_EMBEDDING_PROVIDER: str = "mock"
    DEFAULT_STT_PROVIDER: str = "whisper"
    DEFAULT_TTS_PROVIDER: str = "kokoro"
    
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""

    # Declared so the environment can actually configure them. `model_config`
    # below sets extra="ignore", so an undeclared name set in .env is dropped
    # silently and every getattr(settings, NAME, default) read falls back to its
    # default -- meaning a deployment could set DEEPGRAM_API_KEY or
    # VOICE_PIPELINE_MODE and the app would go on ignoring it. Defaults match the
    # fallbacks already used at each read site, so unset behaviour is unchanged.
    ELEVENLABS_VOICE_ID: str = ""      # app/voice/hybrid_pipeline.py
    DEEPGRAM_API_KEY: str = ""         # app/voice/hybrid_pipeline.py
    JINA_API_KEY: str = ""             # app/matching/jd_scraper.py
    VOICE_PIPELINE_MODE: str = "live"  # app/api/v1/voice_live.py
    
    STORAGE_TYPE: str = "local"
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 10
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Phase 6: Research & Knowledge Base Settings
    RESEARCH_ALLOWED_DOMAINS: List[str] = ["*"]
    RESEARCH_MAX_RESPONSE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    RESEARCH_REQUEST_TIMEOUT_SECONDS: float = 10.0
    RESEARCH_MAX_RETRIES: int = 2
    RESEARCH_BACKOFF_FACTOR: float = 0.5
    RESEARCH_FRESHNESS_HOURS: int = 24
    RESEARCH_ENABLE_PLAYWRIGHT: bool = False
    RESEARCH_USER_AGENT: str = "AI-Interviewer-Research-Bot/1.0 (+https://ai-interviewer.edu)"

    # Phase 8: AI Provider & LLM Resilience Settings
    LLM_DEFAULT_MODEL: str = ""
    LLM_FALLBACK_PROVIDER: str = "mock"
    LLM_ENABLE_FALLBACK: bool = True
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    # These bound how long a candidate can sit staring at "Evaluating answer..."
    # mid-interview. At 30s x 4 attempts a single slow call blocked the turn for
    # over two minutes, which reads as a frozen screen. Every LLM caller on the
    # interview path has a deterministic fallback, so failing fast and degrading
    # is strictly better here than retrying into a stall.
    #
    # The budget must still clear the model's normal answer time, or it discards
    # work that was about to succeed. Measured against gemini-3.5-flash-lite on a
    # real turn-evaluation prompt, five consecutive calls took 13.6, 14.7, 13.8,
    # 17.8 and 18.9 seconds -- so a 25s budget sat inside the ordinary spread,
    # and turns were timing out and being scored by the deterministic rubric even
    # though the provider was healthy. 45s is roughly 2.4x the slowest observed
    # call: comfortably past normal variance, while still bounding the wait.
    LLM_REQUEST_TIMEOUT_SECONDS: float = 45.0
    # Retries for transient faults (429, 5xx, dropped connections). Timeouts are
    # deliberately excluded from this budget -- see app/ai/resilience.py.
    LLM_MAX_RETRIES: int = 1
    LLM_RETRY_BACKOFF_FACTOR: float = 0.5
    LLM_MAX_INPUT_TOKENS: int = 8000
    LLM_CONTEXT_WINDOW_LIMIT: int = 32000

    # Interview turns are latency-critical: the candidate waits on this call
    # between speaking and hearing the next question. flash-lite answers a full
    # evaluation in ~2s. Do NOT swap in a "thinking" model (gemini-3.x-flash /
    # -pro) without also raising LLM_MAX_OUTPUT_TOKENS well above the JSON size
    # -- reasoning tokens are billed against maxOutputTokens, so a thinking
    # model silently truncates the evaluation JSON and the turn falls back to
    # canned output.
    GEMINI_DEFAULT_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_weak_secret_key(cls, v: str) -> str:
        """Reject missing, too-short, or well-known placeholder signing secrets.

        Error messages never include the offending value.
        """
        candidate = (v or "").strip()
        if not candidate:
            raise SecretKeyConfigurationError(
                "SECRET_KEY is not configured. Provide a high-entropy value of at "
                f"least {SECRET_KEY_MIN_LENGTH} characters via the environment or "
                "backend/.env (see .env.example)."
            )
        if len(candidate) < SECRET_KEY_MIN_LENGTH:
            raise SecretKeyConfigurationError(
                f"SECRET_KEY must be at least {SECRET_KEY_MIN_LENGTH} characters. "
                "Set a high-entropy value in the environment (see .env.example)."
            )
        if candidate.lower().startswith(_REJECTED_SECRET_PREFIXES):
            raise SecretKeyConfigurationError(
                "SECRET_KEY is a known placeholder value and cannot be used. "
                "Generate a unique high-entropy secret for this deployment."
            )
        return candidate

    @property
    def allowed_hosts(self) -> List[str]:
        """ALLOWED_HOSTS parsed into a host list (["*"] means any host)."""
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def cors_origins(self) -> List[str]:
        """CORS_ORIGINS as the explicit origin list handed to CORSMiddleware.

        Kept as a parsed string rather than a List[str] field because
        pydantic-settings JSON-decodes complex fields from the environment and
        would reject the comma-separated form used across this repo's configs.
        """
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
