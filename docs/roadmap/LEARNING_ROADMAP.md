# 18-Level Step-by-Step Learning Roadmap

This roadmap organizes the complete project codebase into 18 incremental learning levels for a beginner/intermediate B.Tech student to master, customize, and demonstrate the platform.

```
Level 1  : Project Overview & Architecture Blueprint
Level 2  : Directory Structure & Environment Configurations (.env.example)
Level 3  : Database Models & Schema Design (SQLAlchemy, PostgreSQL, pgvector)
Level 4  : Security & JWT OAuth2 Authentication (passlib, python-jose, RBAC)
Level 5  : AI Provider Abstraction Layer (LLMProvider, Mock, Gemini, OpenAI)
Level 6  : Resume Intelligence & Text Extraction Pipeline (PyPDF2, python-docx)
Level 7  : RAG Knowledge Vector Engine & Chunking (VectorStore, DocumentChunker)
Level 8  : Research Ingestion Pipeline & Crawler (CompanyResearchCrawler)
Level 9  : Question Bank & Dynamic Question Selector
Level 10 : Authoritative Backend Timer & Duration Logic (InterviewTimer)
Level 11 : Deterministic Adaptive State Machine (AdaptiveStateMachine)
Level 12 : Multi-Dimensional Evaluation Rubrics & Scorer (AnswerEvaluator)
Level 13 : Candidate Performance Report Generator (ReportGenerator)
Level 14 : Voice Audio Interfaces — STT & TTS (SpeechToText, TextToSpeech)
Level 15 : Next.js 14 Responsive UI & Glassmorphism Design System (globals.css)
Level 16 : Interactive Interview Rooms (Text, Audio, Video, Monaco Coding)
Level 17 : Automated Testing Strategy (Pytest Unit & Security Test Suites)
Level 18 : DevOps, Docker Compose, & Production Server Deployment
```

## Level Details & Verification Guide

### Level 1 & 2: Architecture & Setup
- Read `docs/architecture/SYSTEM_ARCHITECTURE.md`.
- Inspect `.env.example` and `docker-compose.yml`.

### Level 3 to 5: Core Backend & AI Providers
- Inspect `backend/app/db/models.py` for all 18 database tables.
- Inspect `backend/app/ai/base.py` and `backend/app/ai/mock_provider.py` to understand how the zero-dependency offline fallback works.

### Level 6 to 9: RAG & Resume Pipeline
- Inspect `backend/app/resume/parser.py` to see how explicit facts are separated from model-inferred details.
- Inspect `backend/app/rag/vector_store.py` for cosine similarity vector search.

### Level 10 to 14: Interview Engine & Evaluation
- Inspect `backend/app/interview/state_machine.py` for dynamic difficulty adaptation rules.
- Inspect `backend/app/evaluation/scorer.py` for weighted rubric calculations.

### Level 15 to 18: Frontend & Deployment
- Inspect `frontend/src/app/globals.css` for design system tokens.
- Inspect `frontend/src/app/interview/[id]/page.tsx` for the main room.
- Run `pytest` and launch Docker containers to verify full system functionality.
