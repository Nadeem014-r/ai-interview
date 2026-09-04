import asyncio
import pytest
from app.core.config import settings
from app.core.database import engine
from scripts.cleanup_unwanted_companies import cleanup_database

@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Ensure tests default to mock provider to prevent quota exhaustion and ensure determinism."""
    original_llm = settings.DEFAULT_LLM_PROVIDER
    original_tts = getattr(settings, "DEFAULT_TTS_PROVIDER", "mock")
    original_stt = getattr(settings, "DEFAULT_STT_PROVIDER", "mock")

    settings.DEFAULT_LLM_PROVIDER = "mock"
    settings.DEFAULT_TTS_PROVIDER = "mock"
    settings.DEFAULT_STT_PROVIDER = "mock"

    yield

    settings.DEFAULT_LLM_PROVIDER = original_llm
    settings.DEFAULT_TTS_PROVIDER = original_tts
    settings.DEFAULT_STT_PROVIDER = original_stt

def pytest_sessionfinish(session, exitstatus):
    """Post-test session hook to safely clean up any temporary test records."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def _cleanup():
            await engine.dispose()
            await cleanup_database()
            await engine.dispose()

        loop.run_until_complete(_cleanup())
        loop.close()
    except Exception as e:
        print(f"[conftest] Cleanup error: {e}")
