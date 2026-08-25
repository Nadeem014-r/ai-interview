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

setup_logging()
logger = logging.getLogger("ai_interviewer.main")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="University-Ready AI Interviewer Platform API Engine",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

@app.get("/health", tags=["Health Check"])
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.DEFAULT_LLM_PROVIDER
    }

# Include API v1 Routers
api_v1 = FastAPI()
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

app.mount(settings.API_V1_STR, api_v1)

