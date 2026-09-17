# 🤖 AI Interviewer Platform — University Placement System

A real, modular, secure, and deployable **AI Interviewer Platform** for university students, placement cells, training departments, and candidates.

---

## 🌟 Key Features
- **Deterministic Authoritative Engine**: The backend owns the authoritative countdown timer, interview progression stages (`intro` -> `core` -> `deep_dive` -> `wrapup`), and dynamic difficulty transitions (`easy` -> `medium` -> `hard`).
- **RAG Knowledge Retrieval**: Job description chunks embedded into PostgreSQL `pgvector` for grounded, non-hallucinated technical questioning.
- **Resume Intelligence**: Parses PDF/DOCX resumes, strictly separating explicit verified facts from model-inferred seniority.
- **Multi-Mode Support**: Fully implemented **Text Interview**, **Audio Interview** (Mic -> STT -> Engine -> TTS), **Video Interaction Room**, and **Monaco Coding Sandbox**.
- **Multi-Dimensional Rubric Scoring**: Evaluates candidate answers across 5 weighted dimensions (Correctness: 35%, Relevance: 20%, Reasoning: 20%, Depth: 15%, Communication: 10%).
- **Zero-Dependency Mock Fallback**: Built-in `MockLLMProvider` operates 100% offline without external API keys for demonstration and testing.

---

## 🚀 Technology Stack
- **Backend Framework**: Python FastAPI, Uvicorn, Pydantic v2
- **Database Layer**: PostgreSQL 16 + `pgvector` extension, SQLAlchemy 2.0 (AsyncIO), Alembic
- **AI & RAG Engine**: Google Gemini API, OpenAI API Adapter, Mock Fallback Provider, Cosine Similarity Vector Store
- **Frontend Framework**: Next.js 14 (App Router), React, TypeScript, Vanilla CSS Design System
- **Security & Auth**: OAuth2 JWT, bcrypt, RBAC (`candidate`, `placement_staff`, `admin`), Prompt-Injection Sanitization
- **DevOps & Testing**: Docker, Docker Compose, Pytest AsyncIO

---

## 🛠️ Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (Optional for full containerization)

### 2. Environment Setup
```bash
cd ai-interviewer
cp .env.example .env
```

### 3. Backend Setup & Startup
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# Run Database Seed
python ../database/seed/seed_data.py

# Launch Backend API Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Backend API interactive documentation will be available at `http://localhost:8000/docs`.

### 4. Frontend Setup & Startup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your web browser.

### 5. Docker One-Command Startup
```bash
docker-compose up --build
```

---

## 🖥️ GPU / CPU Notes

Voice inference (Whisper STT, Kokoro TTS) runs locally via `torch` — no external API cost, but it needs RAM/CPU (or GPU) on the host.

- **CPU (default)**: `WHISPER_DEVICE=cpu` in `.env`. No extra setup — this is what `requirements.txt` installs out of the box.
- **GPU**: Set `WHISPER_DEVICE=cuda` and install a CUDA-enabled build of `torch` matching the lab machine's driver **before** `pip install -r requirements.txt` (see [pytorch.org/get-started](https://pytorch.org/get-started/locally/)), then verify with:
  ```bash
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
  ```
- Kokoro TTS uses whatever device `torch` defaults to; it has not been wired to a `KOKORO_DEVICE` setting in this codebase, so it currently runs on CPU even when Whisper is set to `cuda`.
- `PREWARM_VOICE_MODELS=true` loads both models at startup instead of on the first interview (recommended for demos — a cold Kokoro load takes roughly a minute).

---

## 🧪 Running Automated Tests
```bash
cd backend
pytest
```

---

## ⚠️ Known Limitations
- Kokoro TTS has no explicit GPU device switch (see GPU/CPU Notes above) — it runs on CPU regardless of `WHISPER_DEVICE`.
- The background job-description scraper (`ENABLE_BACKGROUND_SCRAPER`) depends on external careers sites that commonly block or rate-limit automated requests.
- `MockLLMProvider` / `LLM_ENABLE_FALLBACK=false` by design: if a real provider is unreachable and no fallback is enabled, affected requests fail closed rather than serving fabricated content — see the inline note in `.env.example`.
- Local voice inference is CPU-bound by default; concurrent interview sessions on a single low-resource machine will see slower transcription/synthesis (tunable via `TTS_MAX_CONCURRENCY` / `STT_MAX_CONCURRENCY`).

## 📌 Current Project Status
Actively developed university placement pilot. Core interview flow (text, audio, video, coding) and the deterministic scoring engine are implemented and covered by the `backend/tests` suite (`pytest`). See [`PROJECT_TECHNICAL_REPORT.md`](PROJECT_TECHNICAL_REPORT.md) and [`docs/roadmap/LEARNING_ROADMAP.md`](docs/roadmap/LEARNING_ROADMAP.md) for a fuller status and design history.

---

## 📄 Project Documentation Links
- [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md)
- [API Documentation](docs/api/API_DOCUMENTATION.md)
- [Security Specification](docs/security/SECURITY_SPECIFICATION.md)
- [AI Resource Optimization Plan](docs/optimization/AI_RESOURCE_OPTIMIZATION_PLAN.md)
- [Academic Project Report](docs/academic/ACADEMIC_PROJECT_REPORT.md)
- [Viva Preparation Guide](docs/viva/VIVA_PREPARATION_GUIDE.md)
- [18-Level Learning Roadmap](docs/roadmap/LEARNING_ROADMAP.md)

---

## 🔒 License
MIT License. Free for university academic submission, student portfolios, and campus placement drives.
