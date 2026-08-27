import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_video_avatar_full_lifecycle():
    unique_email = f"avatar_user_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and Login
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "ValidPassword123!",
            "full_name": "Avatar Test Candidate",
            "role": "candidate"
        })
        assert reg_res.status_code in [200, 201]

        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "ValidPassword123!"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Start Avatar Session
        start_res = await client.post(
            "/api/v1/video/avatar/session/start",
            json={
                "interview_id": 101,
                "avatar_id": "senior_hiring_manager_1",
                "voice_id": "en_us_male_senior"
            },
            headers=headers
        )
        assert start_res.status_code == 201
        start_data = start_res.json()
        assert "session_id" in start_data
        session_id = start_data["session_id"]
        assert start_data["status"] == "connected"
        assert "ice_servers" in start_data

        # 2. Exchange ICE Candidate
        ice_res = await client.post(
            "/api/v1/video/avatar/session/ice",
            json={
                "session_id": session_id,
                "candidate": {
                    "candidate": "candidate:1 1 UDP 2122252543 192.168.1.1 50000 typ host",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0
                }
            },
            headers=headers
        )
        assert ice_res.status_code == 200
        assert ice_res.json()["status"] == "candidate_added"

        # 3. Avatar Speak Request
        speak_res = await client.post(
            "/api/v1/video/avatar/session/speak",
            json={
                "session_id": session_id,
                "text": "Hi, welcome to Google. How is your day going so far?"
            },
            headers=headers
        )
        assert speak_res.status_code == 200
        speak_data = speak_res.json()
        assert speak_data["status"] == "speaking"
        assert "task_id" in speak_data
        assert speak_data["duration_estimated_sec"] > 0

        # 4. Stop Session
        stop_res = await client.post(
            "/api/v1/video/avatar/session/stop",
            json={"session_id": session_id},
            headers=headers
        )
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "closed"

@pytest.mark.asyncio
async def test_video_avatar_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/video/avatar/session/start",
            json={"interview_id": 102}
        )
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_avatar_speak_empty_text_rejected():
    unique_email = f"avatar_val_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "ValidPassword123!",
            "full_name": "Validation Candidate",
            "role": "candidate"
        })
        login_res = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "ValidPassword123!"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        start_res = await client.post(
            "/api/v1/video/avatar/session/start",
            json={"interview_id": 103},
            headers=headers
        )
        session_id = start_res.json()["session_id"]

        speak_res = await client.post(
            "/api/v1/video/avatar/session/speak",
            json={
                "session_id": session_id,
                "text": "   "
            },
            headers=headers
        )
        assert speak_res.status_code in [400, 422]
