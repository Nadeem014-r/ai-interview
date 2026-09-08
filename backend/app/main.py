import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.resume import router as resume_router
from app.api.v1.companies import router as companies_router
from app.api.v1.interviews import router as interviews_router
from app.api.v1.reports import router as reports_router
from app.api.v1.research import router as research_router
from app.api.v1.voice import router as voice_router
from app.api.v1.admin import router as admin_router
from app.api.v1.coding import router as coding_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.video import router as video_router

# ── New voice live router (additive — non-breaking if import fails) ──────────
setup_logging()
logger = logging.getLogger("ai_interviewer.main")

try:
    from app.api.v1.voice_live import router as voice_live_router
    _voice_live_available = True
except ImportError as _e:
    _voice_live_available = False
    logger.warning(f"voice_live router not available (non-fatal): {_e}")



# Interactive API docs publish the full attack surface (every route, parameter
# and schema, including the admin endpoints). They stay on outside production
# and are switched off once ENVIRONMENT=production.
_docs_enabled = settings.ENVIRONMENT.strip().lower() != "production"

# Local voice models are warmed at startup for demo latency. Deployments that
# never use voice can set PREWARM_VOICE_MODELS=false to avoid the RAM, CPU and
# model-download cost entirely; lazy loading still serves any real request.
PREWARM_VOICE_MODELS = os.getenv("PREWARM_VOICE_MODELS", "true").strip().lower() not in ("0", "false", "no")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="University-Ready AI Interviewer Platform API Engine",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS middleware setup. Origins are explicit (never "*") because credentialed
# CORS is only valid against a concrete origin -- browsers reject "*" when
# allow_credentials is on, so the wildcard was both insecure and unreliable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

    # Background warm-up of local AI models (Kokoro TTS & Whisper STT).
    #
    # Only warm a model this deployment actually uses. Both providers load
    # lazily on first use (KokoroTTSProvider._get_pipeline /
    # WhisperSmallSTTProvider._get_pipeline), so warming is a latency
    # optimisation, never a correctness requirement. Warming unconditionally
    # downloaded Kokoro-82M and Whisper weights from HuggingFace on every boot
    # of every worker even when an external TTS/STT provider was configured --
    # paying RAM, CPU, bandwidth and startup time for models never called.
    import asyncio

    def _uses_local(kind: str, local_name: str) -> bool:
        # Mirrors the resolution order in app/ai/factory.py.
        configured = (getattr(settings, f"DEFAULT_{kind}_PROVIDER", "") or "").lower().strip()
        return configured == local_name

    prewarm_tts = PREWARM_VOICE_MODELS and _uses_local("TTS", "kokoro")
    prewarm_stt = PREWARM_VOICE_MODELS and _uses_local("STT", "whisper")

    async def _prewarm_models():
        try:
            if prewarm_tts:
                logger.info("Pre-warming Kokoro TTS model (DEFAULT_TTS_PROVIDER=kokoro)...")
                from app.providers.kokoro_tts import KokoroTTSProvider
                await asyncio.to_thread(KokoroTTSProvider._get_pipeline)
            if prewarm_stt:
                logger.info("Pre-warming Whisper STT model (DEFAULT_STT_PROVIDER=whisper)...")
                from app.providers.whisper_stt import WhisperSmallSTTProvider
                await asyncio.to_thread(WhisperSmallSTTProvider._get_pipeline)
            logger.info("Local voice model pre-warm complete.")
        except Exception as e:
            logger.warning(f"Voice model pre-warming deferred: {e}")

    if prewarm_tts or prewarm_stt:
        asyncio.create_task(_prewarm_models())
    else:
        logger.info(
            "Skipping local voice model pre-warm: no local model is the configured "
            f"provider (TTS={settings.DEFAULT_TTS_PROVIDER}, STT={settings.DEFAULT_STT_PROVIDER}, "
            f"PREWARM_VOICE_MODELS={PREWARM_VOICE_MODELS}). Models still load lazily on first use."
        )

    # ── LLM reachability self-check (non-blocking, logs only) ────────────────
    #
    # A dead or renamed model returns HTTP 404, RoutedLLMProvider fails over to
    # MockLLMProvider, and every question and score from then on is canned --
    # while each request still returns 200. The interview looks like a fixed
    # questionnaire and nothing in the response says why. This probe surfaces
    # that at boot instead of mid-demo. It never blocks startup or fails it.
    async def _check_llm_reachable():
        try:
            from app.ai.factory import AIFactory
            provider = AIFactory.get_llm_provider()
            await provider.generate_text("ping", max_tokens=8, timeout=20.0)
            used = getattr(provider, "last_provider_used", None)
            if used == "mock":
                reason = getattr(provider, "last_fallback_reason", "unknown error")
                logger.error(
                    "LLM SELF-CHECK FAILED: '%s' is unreachable, so interview questions "
                    "and scores will be CANNED MOCK OUTPUT, not real AI. Reason: %s",
                    settings.DEFAULT_LLM_PROVIDER, reason,
                )
            else:
                logger.info(
                    "LLM self-check OK: provider=%s model=%s",
                    settings.DEFAULT_LLM_PROVIDER, settings.GEMINI_DEFAULT_MODEL,
                )
        except Exception as exc:
            logger.error(
                "LLM SELF-CHECK FAILED (%s). Interview turns will fall back to "
                "deterministic/canned output until this is fixed.", exc,
            )

    asyncio.create_task(_check_llm_reachable())

    # ── Background JD scraper (additive — non-blocking) ──────────────────────
    try:
        from app.matching.background_scraper import start_background_scraper
        from app.core.database import AsyncSessionLocal
        start_background_scraper(
            db_factory=AsyncSessionLocal,
            interval_hours=24.0,
        )
        logger.info("Background JD scraper scheduled (24h interval).")
    except Exception as _bg_exc:
        logger.warning(f"Background JD scraper startup failed (non-fatal): {_bg_exc}")


@app.on_event("shutdown")
async def on_shutdown():
    try:
        from app.matching.background_scraper import stop_background_scraper
        stop_background_scraper()
    except Exception:
        pass

@app.get("/health", tags=["Health Check"])
async def health_check():
    """Process-level health plus provider *configuration* status.

    "healthy" means this process is serving. It does not mean the database is
    reachable (see /health/readiness) and it does not mean the AI providers are
    answering -- proving that would require a paid request on every probe.

    `llm_provider` alone was misleading: it reported the configured name even
    when that provider held no credentials and every call was silently served by
    a mock. `llm_provider_configured` reports whether the named provider has what
    it needs to be used at all, checked locally with no external call.
    """
    provider = (settings.DEFAULT_LLM_PROVIDER or "").strip().lower()
    if provider == "gemini":
        configured = bool(settings.GEMINI_API_KEY)
    elif provider == "openai":
        configured = bool(settings.OPENAI_API_KEY)
    else:
        # "mock" and any other explicitly selected provider need no credentials.
        configured = True

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.DEFAULT_LLM_PROVIDER,
        "llm_provider_configured": configured
    }

@app.get("/health/liveness", tags=["Health Check"])
async def liveness_check():
    """Liveness probe: returns 200 if the process is up and running."""
    return {"status": "alive", "timestamp": "ok"}

@app.get("/health/readiness", tags=["Health Check"])
async def readiness_check():
    """Readiness probe: validates database connectivity before accepting traffic."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "disconnected"})

# Include API v1 Routers
api_v1 = FastAPI(
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
api_v1.include_router(auth_router)
api_v1.include_router(profile_router)
api_v1.include_router(resume_router)
api_v1.include_router(companies_router)
api_v1.include_router(jobs_router)
api_v1.include_router(interviews_router)
api_v1.include_router(reports_router)
api_v1.include_router(research_router)
api_v1.include_router(voice_router)
api_v1.include_router(admin_router)
api_v1.include_router(coding_router)
api_v1.include_router(video_router)

# ── New live voice WebSocket router (additive) ────────────────────────────────
if _voice_live_available:
    app.include_router(voice_live_router)  # WebSocket routes registered on app directly
    logger.info("Live voice WebSocket routes registered: /ws/voice/live, /ws/voice/hybrid")

app.mount(settings.API_V1_STR, api_v1)

