# AI Resource Optimization Plan — Cost & Token Minimization Architecture

## 1. Core Cost Efficiency Strategy
To prevent expensive LLM token consumption and API cost overruns during high-volume university placement drives, the platform adheres to the following optimization rules:

```
                  ┌──────────────────────────────────────────────┐
                  │           User Question Request              │
                  └──────────────────────┬───────────────────────┘
                                         │
                         Is Question in Question Bank?
                                  /            \
                             YES /              \ NO
                                v                v
                    ┌─────────────────┐   ┌──────────────────────────┐
                    │ Return Question │   │ Query RAG Vector Store   │
                    │   (0 LLM Cost)  │   │  (Minimal Context Chunks)│
                    └─────────────────┘   └────────────┬─────────────┘
                                                       │
                                                       v
                                          ┌──────────────────────────┐
                                          │ Call Fast Tier Model     │
                                          │ (e.g. Gemini 1.5 Flash)  │
                                          └──────────────────────────┘
```

## 2. Multi-Tier Model Selection Architecture

| Module / Operation | Model Tier | Rationale | Cost Factor |
|---|---|---|---|
| Question Selection | Question Bank / Local DB | Pre-curated questions prioritized first | 0x |
| Vector Embeddings | `text-embedding-004` / Mock | Compact vector representations | 0.01x |
| Resume Intelligence | `gemini-1.5-flash` / Mock | Fast JSON structured output | 0.1x |
| Turn Evaluation | `gemini-1.5-flash` / Mock | Compact structured rubric scoring | 0.1x |
| Report Synthesis | `gemini-1.5-flash` / Mock | End-of-interview aggregation only | 0.2x |

## 3. Key Optimization Mechanisms

### 3.1 Prompt Compression & Context Truncation
- Rather than appending full multi-turn conversation histories (which grows quadratically in token cost), the backend maintains a **compact structured state object** (`InterviewState`).
- On every turn, only the **current question** and **candidate answer** are sent to the LLM evaluator alongside expected concept keywords.

### 3.2 Question Bank Prioritization
- The system checks the database `questions` table first. LLM question generation is triggered **only** when un-asked questions for a specific topic/difficulty are exhausted.

### 3.3 Audio/STT Optimization
- Voice recordings are transcribed once via STT service upon submission. Transcripts are cached in the `answers` database table to prevent re-transcription.
