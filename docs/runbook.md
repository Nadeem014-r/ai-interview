# AI Interviewer — Site Reliability Engineering Operational Runbook (Phase 10H)

## Incident Response Standard Operating Procedures (SOPs)

---

### 1. Redis Cache Outage (`REDIS_DOWN`)
- **Severity**: WARNING / DEGRADED
- **Symptom**: Readiness endpoint reports Redis degraded; metrics report `redis_failures`.
- **Automated Mitigation**: Phase 10G/10H automatically engages in-memory fallback; interview state remains persisted in PostgreSQL.
- **Remediation Steps**:
  1. Inspect Redis container: `docker compose -f docker-compose.production.yml logs redis --tail=100`
  2. Verify RAM usage: `docker stats redis`
  3. Restart container: `docker compose -f docker-compose.production.yml restart redis`

---

### 2. PostgreSQL Outage (`DATABASE_DOWN`)
- **Severity**: CRITICAL
- **Symptom**: Readiness reports `unhealthy`; new interview starts return 503.
- **Remediation Steps**:
  1. Check PostgreSQL status: `docker compose -f docker-compose.production.yml ps postgres`
  2. Inspect storage disk space: `df -h`
  3. Verify connection logs: `docker compose -f docker-compose.production.yml logs postgres --tail=100`
  4. Restart database: `docker compose -f docker-compose.production.yml restart postgres`

---

### 3. AI Provider Outage (`AI_PROVIDER_FAILURE`)
- **Severity**: WARNING
- **Symptom**: STT / TTS latency spikes or provider API returns 5xx / 429 quota exhaustion.
- **Automated Mitigation**: Circuit breaker trips to OPEN; `FallbackTTSProvider` cascades to secondary TTS.
- **Remediation Steps**:
  1. Verify active fallback status in `/health/ready`.
  2. Check provider account quotas for ElevenLabs / Gemini / OpenAI.
  3. Update `ELEVENLABS_API_KEY` or `GEMINI_API_KEY` in `.env` and restart backend.

---

### 4. WebSocket / Reconnect Surge (`RECONNECT_STORM`)
- **Severity**: WARNING
- **Symptom**: High reconnect rate per second.
- **Automated Mitigation**: Phase 10G `RealtimeTransportHardening` rate-limits reconnect floods and deduplicates replayed messages.
- **Remediation Steps**:
  1. Inspect active connection count in metrics.
  2. Verify network connectivity between reverse proxy and backend.
