# University Pilot Operations & Runbook

## 1. Routine Operations
- **Startup**: Launch database service -> launch backend API via Uvicorn -> launch Next.js frontend.
- **Monitoring**: Check `/health/readiness` and inspect logs in `logs/` or stdout.
- **Backups**: Perform periodic pg_dump backups of the PostgreSQL database:
  ```bash
  pg_dump -U postgres -h localhost ai_interviewer > backup_$(date +%Y%m%d).sql
  ```

## 2. Incident & Failure Recovery
- **AI / LLM Outage (Gemini)**: The engine automatically falls back to grounded deterministic question templates and structured rubrics with zero interruption.
- **TTS Outage (ElevenLabs)**: Audio synthesis falls back gracefully; the text question is displayed on screen and synthesized speech retries.
- **STT Failure**: Candidate answers can be edited or submitted via text mode without losing turn context.
- **Database Connection Loss**: `/health/readiness` returns `503 Service Unavailable`; sessions in progress are safely committed upon reconnection.

## 3. Database Disaster Recovery
```bash
psql -U postgres -h localhost -d ai_interviewer < backup_YYYYMMDD.sql
```
