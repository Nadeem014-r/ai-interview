import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "AI Interviewer Platform"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-this-ultra-secure-secret-key-for-jwt-signing-minimum-32-chars!"
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_HOSTS: List[str] = ["*"]
    
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_interviewer_db"
    DATABASE_URL: str ="postgresql+asyncpg://postgres:Nadeem%40123@localhost:5432/ai_interviewer_db" # Default fallback for zero-dependency dev mode
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    DEFAULT_LLM_PROVIDER: str = "mock"
    DEFAULT_EMBEDDING_PROVIDER: str = "mock"
    DEFAULT_STT_PROVIDER: str = "mock"
    DEFAULT_TTS_PROVIDER: str = "mock"
    
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    
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
    LLM_REQUEST_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BACKOFF_FACTOR: float = 0.5
    LLM_MAX_INPUT_TOKENS: int = 8000
    LLM_CONTEXT_WINDOW_LIMIT: int = 32000

    GEMINI_DEFAULT_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
