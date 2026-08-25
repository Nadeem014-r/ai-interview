import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_auth_and_profile_flow():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user
        reg_payload = {
            "email": unique_email,
            "password": "ValidPassword123!",
            "full_name": "Test Candidate Flow",
            "role": "candidate"
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code in [200, 201]

        # Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "ValidPassword123!"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get Profile
        prof_res = await client.get("/api/v1/profile", headers=headers)
        assert prof_res.status_code == 200
        assert prof_res.json()["full_name"] == "Test Candidate Flow"

        # Update Profile
        update_payload = {
            "full_name": "Test Candidate Flow Updated",
            "headline": "Full-Stack Software Engineer",
            "phone": "+1 555-019-2834",
            "university": "State Tech University",
            "degree": "B.Tech",
            "branch": "Computer Science",
            "graduation_year": 2025,
            "skills": ["Python", "FastAPI", "Docker", "SQL"],
            "experience_level": "entry"
        }
        put_res = await client.put("/api/v1/profile", json=update_payload, headers=headers)
        assert put_res.status_code == 200
        assert put_res.json()["headline"] == "Full-Stack Software Engineer"
        assert "Python" in put_res.json()["skills"]

@pytest.mark.asyncio
async def test_job_matching_api():
    unique_email = f"matcher_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "ValidPassword123!",
            "full_name": "Matcher Candidate",
            "role": "candidate"
        })
        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "ValidPassword123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get job recommendations
        match_res = await client.get("/api/v1/jobs/matches", headers=headers)
        assert match_res.status_code == 200
        matches = match_res.json()
        assert isinstance(matches, list)
        if len(matches) > 0:
            first_match = matches[0]
            assert "role_title" in first_match
            assert "overall_score" in first_match
            assert "matched_skills" in first_match

@pytest.mark.asyncio
async def test_adaptive_interview_lifecycle():
    unique_email = f"interview_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "ValidPassword123!",
            "full_name": "Interview Candidate",
            "role": "candidate"
        })
        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "ValidPassword123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create interview
        create_payload = {
            "company_id": 1,
            "role_id": 1,
            "mode": "text",
            "interview_type": "technical",
            "duration_minutes": 15,
            "target_level": "entry"
        }
        create_res = await client.post("/api/v1/interviews", json=create_payload, headers=headers)
        assert create_res.status_code in [200, 201]
        interview = create_res.json()
        interview_id = interview["id"]
        assert interview["current_question"] is not None
        assert len(interview["current_question"]["question_text"]) > 0

        # Retrieve interview session
        get_res = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == interview_id
        assert get_res.json()["current_question"] is not None

        # Submit answer turn
        ans_res = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={"answer_text": "In B-tree indexing, nodes keep sorted keys to allow logarithmic search complexity while reducing random disk block accesses."},
            headers=headers
        )
        assert ans_res.status_code == 200
        turn_data = ans_res.json()
        assert "evaluation" in turn_data
        assert turn_data["evaluation"]["overall_question_score"] > 0

        # Finish interview early
        finish_res = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
        assert finish_res.status_code == 200
        assert "report_id" in finish_res.json()

        # Check Report
        report_res = await client.get(f"/api/v1/reports/{interview_id}", headers=headers)
        assert report_res.status_code == 200
        rep = report_res.json()
        assert rep["overall_score"] > 0
        assert len(rep["strengths"]) > 0
        assert len(rep["recommendations"]) > 0
