import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db

@pytest.mark.asyncio
async def test_user_isolation_security():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register User 1
        await client.post("/api/v1/auth/register", json={
            "email": "user1@example.com",
            "password": "Password123!",
            "full_name": "User One",
            "role": "candidate"
        })
        login_u1 = await client.post("/api/v1/auth/login", json={
            "email": "user1@example.com",
            "password": "Password123!"
        })
        token1 = login_u1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Register User 2
        await client.post("/api/v1/auth/register", json={
            "email": "user2@example.com",
            "password": "Password123!",
            "full_name": "User Two",
            "role": "candidate"
        })
        login_u2 = await client.post("/api/v1/auth/login", json={
            "email": "user2@example.com",
            "password": "Password123!"
        })
        token2 = login_u2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates an interview session
        create_res = await client.post("/api/v1/interviews", json={
            "company_id": 1,
            "role_id": 1,
            "mode": "text",
            "duration_minutes": 15,
            "target_level": "entry"
        }, headers=headers1)
        int_id = create_res.json()["id"]

        # User 2 attempts to fetch User 1's interview session -> Should return 403 Forbidden
        u2_int_res = await client.get(f"/api/v1/interviews/{int_id}", headers=headers2)
        assert u2_int_res.status_code == 403

        # User 2 attempts to submit an answer to User 1's interview -> Should return 403 Forbidden
        u2_ans_res = await client.post(f"/api/v1/interviews/{int_id}/answer", json={
            "answer_text": "Hacking answer"
        }, headers=headers2)
        assert u2_ans_res.status_code == 403

        # User 2 attempts to view User 1's report -> Should return 403 Forbidden
        u2_rep_res = await client.get(f"/api/v1/reports/{int_id}", headers=headers2)
        assert u2_rep_res.status_code == 403
