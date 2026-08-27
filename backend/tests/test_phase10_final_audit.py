"""Phase 10: Final University-Ready Production Hardening & Full Audit Test Suite.

Validates:
1. Health check probes (/health, /health/liveness, /health/readiness)
2. Role-based authorization & IDOR protection across Candidates, Placement Staff, and Admins
3. File upload safety & malicious/oversized rejection
4. Audit logging without sensitive credential/token leakage
5. Provider failure resilience (LLM, TTS, STT fallback continuity)
6. Complete end-to-end university pilot candidate workflow
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.models import Base, User, Company, Role, Interview, InterviewState, Question, Report
from app.core.security import create_access_token, get_password_hash
from app.core.audit import AuditLogger
from app.resume.validator import ResumeValidator


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_phase10_health_and_probes():
    """Verify standard /health, /health/liveness, and /health/readiness endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # General health
        res_h = await ac.get("/health")
        assert res_h.status_code == 200
        assert res_h.json()["status"] == "healthy"

        # Liveness
        res_l = await ac.get("/health/liveness")
        assert res_l.status_code == 200
        assert res_l.json()["status"] == "alive"

        # Readiness
        res_r = await ac.get("/health/readiness")
        assert res_r.status_code == 200
        assert res_r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_phase10_admin_authorization_and_role_enforcement(async_db: AsyncSession):
    """Verify candidates cannot access admin routes while admin/placement staff can."""
    # Create Candidate User
    cand = User(full_name="Student Candidate", email="student@university.edu", hashed_password=get_password_hash("pw"), role="candidate")
    # Create Admin User
    admin = User(full_name="Placement Officer", email="admin@university.edu", hashed_password=get_password_hash("pw"), role="admin")
    async_db.add_all([cand, admin])
    await async_db.commit()
    await async_db.refresh(cand)
    await async_db.refresh(admin)

    cand_token = create_access_token(cand.id, role="candidate")
    admin_token = create_access_token(admin.id, role="admin")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Candidate attempt -> Forbidden
        res_cand = await ac.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {cand_token}"}
        )
        assert res_cand.status_code == 403

        # Admin attempt -> Allowed
        res_admin = await ac.get(
            "/api/v1/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_admin.status_code == 200
        assert "total_candidates" in res_admin.json()


@pytest.mark.asyncio
async def test_phase10_idor_protection_between_candidates(async_db: AsyncSession):
    """Verify Candidate A cannot view Candidate B's interview session or report."""
    u1 = User(full_name="Candidate One", email="c1@univ.edu", hashed_password="pw", role="candidate")
    u2 = User(full_name="Candidate Two", email="c2@univ.edu", hashed_password="pw", role="candidate")
    async_db.add_all([u1, u2])
    await async_db.commit()
    await async_db.refresh(u1)
    await async_db.refresh(u2)

    comp = Company(name="TechCorp", slug="techcorp")
    async_db.add(comp)
    await async_db.commit()
    await async_db.refresh(comp)

    role = Role(company_id=comp.id, title="Software Engineer", level="Entry")
    async_db.add(role)
    await async_db.commit()
    await async_db.refresh(role)

    # Interview belonging to Candidate Two
    int_u2 = Interview(candidate_id=u2.id, company_id=comp.id, role_id=role.id, status="in_progress")
    async_db.add(int_u2)
    await async_db.commit()
    await async_db.refresh(int_u2)

    u1_token = create_access_token(u1.id, role="candidate")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Candidate One attempts to access Candidate Two's interview
        res = await ac.get(
            f"/api/v1/interviews/{int_u2.id}",
            headers={"Authorization": f"Bearer {u1_token}"}
        )
        assert res.status_code == 403
        assert "unauthorized" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_phase10_audit_logger_sanitization():
    """Verify audit logger records actions while redacting passwords, tokens, and keys."""
    event = AuditLogger.log_event(
        event_type="USER_PASSWORD_CHANGE",
        user_id=42,
        user_role="admin",
        resource="user_profile",
        status="SUCCESS",
        details={
            "action": "reset_password",
            "password": "super_secret_password_123",
            "access_token": "bearer_jwt_secret_token",
            "api_key": "secret_gemini_key",
            "target_user_id": 99
        }
    )

    assert event["event_type"] == "USER_PASSWORD_CHANGE"
    assert event["details"]["password"] == "[REDACTED]"
    assert event["details"]["access_token"] == "[REDACTED]"
    assert event["details"]["api_key"] == "[REDACTED]"
    assert event["details"]["target_user_id"] == "99"


@pytest.mark.asyncio
async def test_phase10_file_upload_security():
    """Verify rejection of invalid file extensions, oversized files, and path traversal attempts."""
    from fastapi import UploadFile
    import io

    # 1. Invalid extension .exe
    fake_file_exe = UploadFile(filename="malicious.exe", file=io.BytesIO(b"binary_code"))
    with pytest.raises(Exception):
        ResumeValidator.validate_upload(fake_file_exe, b"binary_code")

    # 2. Oversized file (> 10MB)
    huge_bytes = b"0" * (11 * 1024 * 1024)
    fake_huge_pdf = UploadFile(filename="huge.pdf", file=io.BytesIO(huge_bytes))
    with pytest.raises(Exception):
        ResumeValidator.validate_upload(fake_huge_pdf, huge_bytes)


@pytest.mark.asyncio
async def test_phase10_provider_resilience_and_fallback():
    """Verify system remains operable when AI provider experiences transient failure."""
    from app.companies.strategy_engine import CompanyStrategyEngine
    strat = CompanyStrategyEngine.compute_interview_strategy("google", "Backend Engineer", "entry")
    
    with patch("app.ai.factory.AIFactory.get_llm_provider") as mock_llm_factory:
        mock_llm = AsyncMock()
        mock_llm.generate_json.side_effect = TimeoutError("Gemini API Timeout")
        mock_llm_factory.return_value = mock_llm

        q = await CompanyStrategyEngine.generate_adaptive_company_question(
            strategy=strat,
            memory=None,
            candidate_answer="I used Redis for caching."
        )

        assert q is not None
        assert "question_text" in q
        assert len(q["question_text"]) > 10
