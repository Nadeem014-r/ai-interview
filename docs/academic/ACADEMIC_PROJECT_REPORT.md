# Academic Project Report — AI Interviewer Platform

**Degree**: Bachelor of Technology (B.Tech) in Computer Science & Engineering  
**Project Title**: AI-Powered Adaptive Mock Interviewer & Candidate Performance Evaluator System  

---

## Abstract
Campus placement drives represent a critical milestone in engineering education. However, traditional manual mock interview sessions suffer from scalability constraints, evaluator bias, and lack of objective, structured rubric feedback. This project presents the **AI Interviewer Platform**, a full-stack automated adaptive mock interview system. Built using FastAPI, Next.js 14, PostgreSQL with pgvector, and Google Gemini AI model abstractions, the platform delivers real-time adaptive technical questioning, company-grounded RAG intelligence, and weighted rubric evaluation across text, audio, and video interaction modes. The platform features an authoritative backend state machine, zero-dependency offline fallback capabilities, prompt-injection security controls, and resource optimization pipelines suitable for university deployment.

---

## 1. Introduction & Objectives

### 1.1 Problem Statement
1. Limited availability of senior technical alumni and faculty to conduct one-on-one mock interviews for hundreds of graduating candidates.
2. Inconsistent and subjective evaluation metrics lacking actionable, rubric-grounded feedback.
3. Chatbot-style tools that lack authoritative state tracking, leading to prompt hallucination, unconstrained interview timers, and high API token costs.

### 1.2 Objectives
- Build a full-stack platform capable of evaluating candidates across multiple interview modes (Text, Audio, Video).
- Develop an authoritative backend state machine to regulate question difficulty, topic coverage, and timer logic deterministically.
- Implement Retrieval-Augmented Generation (RAG) using pgvector to ground technical questions in company job specifications.
- Provide comprehensive candidate performance reports featuring weighted rubric score breakdowns and actionable recommendations.

---

## 2. Literature Survey & System Comparison

| System Feature | Generic LLM Chatbot | Traditional LMS | This Project (AI Interviewer) |
|---|---|---|---|
| Timer Control | Frontend / LLM Prompt | Static Quiz Timer | Authoritative Backend Timer |
| Difficulty Transition | Unpredictable / Static | Manual | Deterministic Adaptive State Machine |
| Company Knowledge | Web Pre-training Memory | None | RAG (pgvector Cosine Similarity) |
| Scoring Methodology | Unstructured LLM Score | Multiple Choice | Multi-Dimensional Weighted Rubric |
| Offline Fallback | Fails without API Key | N/A | Mock Provider Architecture |

---

## 3. Methodology & System Architecture

### 3.1 Adaptive State Machine Algorithm
The interview progression is governed by the pure function:
\[
S_{t+1} = \delta(S_t, E_t)
\]
Where \(S_t\) represents the current interview state (topic, difficulty, covered topics, time remaining) and \(E_t\) represents the empirical evaluation score (0-10) of the candidate's response.

### 3.2 Evaluation Rubric Weighting Equation
\[
\text{Overall Score} = \sum_{i=1}^{n} w_i \cdot s_i
\]
Where weights \(w_i\) are assigned as: Correctness (\(0.35\)), Relevance (\(0.20\)), Reasoning (\(0.20\)), Depth (\(0.15\)), and Communication (\(0.10\)).

---

## 4. Conclusion & Future Scope
The AI Interviewer Platform successfully addresses scalability and evaluation consistency challenges in campus placement drives. Future enhancements include expanding coding sandbox execution environments, integrating real-time WebRTC audio streaming, and deploying automated resume ATS score benchmarking.
