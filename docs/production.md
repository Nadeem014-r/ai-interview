# AI Interviewer — Production Deployment, Reliability & Operations Guide

## Overview
Phase 10F operationalizes the AI Interviewer platform for containerized production deployment behind reverse proxies with TLS termination, multi-tier health endpoints, PostgreSQL/Redis resilience, secret redaction, and bounded background supervision.

---

## Infrastructure Topology
```
Candidate Browser
       ↓ (HTTPS / WSS)
NGINX / Caddy Reverse Proxy (TLS termination, WebSocket upgrade, security headers)
       ↓
FastAPI Backend (Uvicorn 4 workers, non-root appuser)
       ↓
PostgreSQL 15 (Persistent volume, connection pre-ping)
       ↓
Redis 7 (Persistent volume, session caching & pub/sub)
       ↓
Isolated Phase 1–10E Application Core
```

---

## Pre-Flight Checklist
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] High-entropy `SECRET_KEY` (minimum 32 characters)
- [ ] Explicit non-wildcard `ALLOWED_HOSTS` and `CORS_ORIGINS`
- [ ] Production PostgreSQL connection string (`DATABASE_URL`)
- [ ] Redis service reachable (`REDIS_URL`)
- [ ] Volume mounts for `/app/data/storage`

---

## Deployment Commands
```bash
# 1. Prepare environment secrets
cp .env.example .env
# Edit .env with production credentials

# 2. Launch production stack with Docker Compose
docker compose -f docker-compose.production.yml up --build -d

# 3. Verify health & readiness
curl -f http://localhost:8000/docs
docker compose -f docker-compose.production.yml ps
```

---

## Health & Diagnostics
- **Liveness (`/health/live`)**: Validates process execution and responsiveness without depending on external databases.
- **Readiness (`/health/ready`)**: Validates PostgreSQL connectivity, Redis latency, storage availability, and security configuration.
