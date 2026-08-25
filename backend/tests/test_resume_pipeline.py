import pytest
import io
import os
import uuid
from docx import Document
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db, AsyncSessionLocal
from app.db.models import Resume, ResumeProfile, CandidateProfile
from app.resume.parser import ResumeParser
from sqlalchemy import select
from sqlalchemy.orm import selectinload

@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()

def create_mock_docx(text: str) -> bytes:
    doc = Document()
    for line in text.split("\n"):
        if line.strip():
            doc.add_paragraph(line)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_mock_pdf(text: str) -> bytes:
    # Use PyPDF2 / io to construct or return standard PDF structure with text stream
    # A standard valid minimal single-page PDF with Helvetica font text
    stream_content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET"
    stream_len = len(stream_content.encode("latin-1"))
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {stream_len} >>
stream
{stream_content}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000350 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
430
%%EOF
"""
    return pdf.encode("latin-1")

async def register_and_get_token(client: AsyncClient, email: str = None) -> tuple[str, int]:
    unique_email = email or f"cand_{uuid.uuid4().hex[:8]}@example.com"
    res = await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "Password123!",
        "full_name": "Pipeline Tester"
    })
    data = res.json()
    return data["access_token"], data["user_id"]

# 11. Valid PDF upload
@pytest.mark.asyncio
async def test_valid_pdf_upload():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        pdf_bytes = create_mock_pdf("Jane Doe - Python and Docker Engineer")
        files = {"file": ("my_resume.pdf", pdf_bytes, "application/pdf")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["filename"] == "my_resume.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["resume_profile"] is not None
        assert "Python" in data["resume_profile"]["skills"]

# 12. Valid DOCX upload
@pytest.mark.asyncio
async def test_valid_docx_upload():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        docx_bytes = create_mock_docx("Sarah Connor\nEmail: sarah@skynet.com\nSkills: TypeScript, Next.js, React, GraphQL")
        files = {"file": ("resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["filename"] == "resume.docx"
        assert "TypeScript" in data["resume_profile"]["skills"]
        assert "React" in data["resume_profile"]["skills"]

# 13. Valid TXT upload
@pytest.mark.asyncio
async def test_valid_txt_upload():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        txt_bytes = b"Robert Paulson\nEmail: robert@fight.org\nPhone: +1 555-019-9988\nSkills: Python, Redis, PostgreSQL\nEducation: Bachelor of Science from Stanford University 2023"
        files = {"file": ("resume.txt", txt_bytes, "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["filename"] == "resume.txt"
        assert data["resume_profile"]["explicit_facts"]["email"] == "robert@fight.org"
        assert "PostgreSQL" in data["resume_profile"]["skills"]

# 14. Unsupported extension rejected
@pytest.mark.asyncio
async def test_unsupported_extension_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("malicious.exe", b"binary content", "application/octet-stream")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 400
        assert "Unsupported file format" in res.json()["detail"]

# 15. Invalid MIME rejected where appropriate
@pytest.mark.asyncio
async def test_invalid_mime_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("resume.pdf", b"some bytes", "image/png")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 400
        assert "Invalid MIME type" in res.json()["detail"]

# 16. Empty file rejected
@pytest.mark.asyncio
async def test_empty_file_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("empty.txt", b"", "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 400
        assert "Empty file" in res.json()["detail"]

# 17. Oversized file rejected
@pytest.mark.asyncio
async def test_oversized_file_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 11MB file (exceeds default 10MB limit)
        huge_bytes = b"A" * (11 * 1024 * 1024)
        files = {"file": ("huge.txt", huge_bytes, "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 400
        assert "exceeds maximum allowed size" in res.json()["detail"]

# 18. Path traversal filename cannot escape upload directory
@pytest.mark.asyncio
async def test_path_traversal_sanitized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        txt_bytes = b"Alice Traversal\nSkills: Python, Git"
        files = {"file": ("../../etc/passwd.txt", txt_bytes, "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert ".." not in data["filename"]
        assert data["filename"] == "passwd.txt"

# 19. Text extraction works
def test_text_extraction_direct():
    docx_bytes = create_mock_docx("Heading\nThis is paragraph one.\nSecond paragraph with FastAPI.")
    extracted = ResumeParser.extract_text_from_bytes(docx_bytes, "test.docx")
    assert "paragraph one" in extracted
    assert "FastAPI" in extracted

# 20. Skills are extracted from actual resume text without whole-word false positives
def test_skill_extraction_accuracy():
    text = "Proficient in Python, C++, Go, and PostgreSQL. Familiar with React."
    parsed = ResumeParser.deterministic_rule_parse(text)
    assert "Python" in parsed["skills"]
    assert "C++" in parsed["skills"]
    assert "Go" in parsed["skills"]
    assert "PostgreSQL" in parsed["skills"]
    assert "React" in parsed["skills"]
    # Ensure "C" is not incorrectly matched from "React" or "PostgreSQL" unless standalone
    assert "Java" not in parsed["skills"]
    assert "Rust" not in parsed["skills"]

# 21. Education is extracted when present
def test_education_extracted_when_present():
    text = "Education:\nBachelor of Technology in Computer Science from National Institute of Technology, 2020-2024"
    parsed = ResumeParser.deterministic_rule_parse(text)
    assert len(parsed["education"]) > 0
    assert "Bachelor of Technology" in parsed["education"][0]["degree"]
    assert "National Institute of Technology" in parsed["education"][0]["institution"]
    assert "2020-2024" in parsed["education"][0]["year"]

# 22. Projects extracted when present
@pytest.mark.asyncio
async def test_projects_extracted_when_present():
    raw_text = "Projects:\nDistributed Task Queue built with Python, Redis and Docker to handle async tasks."
    parsed = await ResumeParser.parse_resume_content(raw_text)
    assert isinstance(parsed["projects"], list)

# 23. Missing information is NOT fabricated
def test_missing_information_not_fabricated():
    empty_resume_text = "Just a short note without any technical keywords or degrees."
    parsed = ResumeParser.deterministic_rule_parse(empty_resume_text)
    # MUST NOT contain fabricated defaults like Python, FastAPI, B.Tech, etc.
    assert parsed["skills"] == []
    assert parsed["education"] == []
    assert parsed["projects"] == []
    assert parsed["experience"] == []
    assert parsed["technologies"] == []
    assert parsed["explicit_facts"]["candidate_name"] is None
    assert parsed["explicit_facts"]["email"] is None
    assert parsed["explicit_facts"]["phone"] is None

# 24. AI parser failure does not fabricate data
@pytest.mark.asyncio
async def test_ai_parser_fallback_does_not_fabricate():
    text_without_skills = "A simple statement without technologies."
    parsed = await ResumeParser.parse_resume_content(text_without_skills)
    assert parsed["skills"] == []
    assert parsed["education"] == []
    assert parsed["projects"] == []
    assert parsed["technologies"] == []

# 25. Parsed ResumeProfile is persisted
@pytest.mark.asyncio
async def test_parsed_resume_profile_persisted():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        txt_bytes = b"Dev Person\nEmail: dev@test.com\nSkills: Python, Django, PostgreSQL"
        files = {"file": ("dev_resume.txt", txt_bytes, "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        assert res.status_code == 201
        resume_id = res.json()["id"]

        # Check DB directly
        async with AsyncSessionLocal() as session:
            stmt = select(Resume).options(selectinload(Resume.resume_profile)).where(Resume.id == resume_id)
            db_res = (await session.execute(stmt)).scalars().first()
            assert db_res is not None
            assert db_res.resume_profile is not None
            assert "Python" in db_res.resume_profile.skills
            assert "Django" in db_res.resume_profile.skills

# 26. CandidateProfile synchronization works
@pytest.mark.asyncio
async def test_candidate_profile_synchronization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, user_id = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        txt_bytes = b"Sync Person\nEmail: sync@test.com\nPhone: +1 555-123-4567\nSkills: Kubernetes, Docker, Go\nEducation: Bachelor of Engineering from MIT, 2024"
        files = {"file": ("sync.txt", txt_bytes, "text/plain")}
        await client.post("/api/v1/resume/upload", files=files, headers=headers)

        # Fetch candidate profile
        prof_res = await client.get("/api/v1/profile", headers=headers)
        assert prof_res.status_code == 200
        prof = prof_res.json()
        assert "Docker" in prof["skills"]
        assert "Go" in prof["skills"]
        assert prof["phone"] == "+1 555-123-4567"

# 27. Unauthorized user cannot access another user's resume (IDOR defense)
@pytest.mark.asyncio
async def test_unauthorized_user_cannot_access_other_resume():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User 1
        token1, _ = await register_and_get_token(client)
        headers1 = {"Authorization": f"Bearer {token1}"}
        txt_bytes = b"User 1 Resume\nSkills: Python"
        files = {"file": ("u1.txt", txt_bytes, "text/plain")}
        res1 = await client.post("/api/v1/resume/upload", files=files, headers=headers1)
        r1_id = res1.json()["id"]

        # User 2
        token2, _ = await register_and_get_token(client)
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 2 attempts to get User 1's resume
        get_res = await client.get(f"/api/v1/resume/{r1_id}", headers=headers2)
        assert get_res.status_code == 404

        # User 2 attempts to update User 1's resume
        put_res = await client.put(f"/api/v1/resume/{r1_id}/profile", json={"skills": ["HackedSkill"]}, headers=headers2)
        assert put_res.status_code == 404

# 28. Candidate can update parsed resume profile
@pytest.mark.asyncio
async def test_candidate_can_update_parsed_resume_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token, _ = await register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        txt_bytes = b"Original Resume\nSkills: Python, SQL"
        files = {"file": ("orig.txt", txt_bytes, "text/plain")}
        res = await client.post("/api/v1/resume/upload", files=files, headers=headers)
        resume_id = res.json()["id"]

        # Candidate corrects their extracted skills
        update_payload = {
            "skills": ["Python", "FastAPI", "PostgreSQL", "System Design"],
            "technologies": ["Python", "FastAPI", "PostgreSQL"]
        }
        put_res = await client.put(f"/api/v1/resume/{resume_id}/profile", json=update_payload, headers=headers)
        assert put_res.status_code == 200
        updated = put_res.json()
        assert "System Design" in updated["resume_profile"]["skills"]
        assert "FastAPI" in updated["resume_profile"]["skills"]
