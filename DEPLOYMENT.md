# University Pilot Deployment Guide

## 1. Prerequisites
- **Python**: 3.10+ (tested on Python 3.13)
- **Node.js**: 18+ (tested on Node 20 / Next.js 14)
- **PostgreSQL**: 14+ (or local SQLite for lightweight testing)
- **Redis** (Optional): For high-throughput caching and distributed state

## 2. Environment Configuration
Create a `.env` file in `backend/` based on `.env.example`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interviewer
SECRET_KEY=your-secure-jwt-secret-key
ENVIRONMENT=production
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-google-gemini-api-key
DEFAULT_TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ID=hqBknhU0QebV576rq8S9
DEFAULT_STT_PROVIDER=whisper
OPENAI_API_KEY=your-openai-whisper-api-key
```

## 3. Backend Setup & Startup
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 4. Frontend Setup & Build
```powershell
cd frontend
npm install
npm run build
npm run start
```

## 5. Health Check Probes
- **General Health**: `GET /health` -> `{"status": "healthy"}`
- **Liveness Probe**: `GET /health/liveness` -> `{"status": "alive"}`
- **Readiness Probe**: `GET /health/readiness` -> `{"status": "ready", "database": "connected"}`
