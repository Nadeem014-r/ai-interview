# REST API Documentation — AI Interviewer Platform (v1)

Base URL: `http://localhost:8000/api/v1`

## 1. Authentication Endpoint Matrix

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/auth/register` | Register new user (candidate/staff/admin) | No |
| `POST` | `/auth/login` | Authenticate & issue JWT access token | No |
| `GET` | `/profile` | Fetch current user candidate profile | Yes (JWT) |
| `PUT` | `/profile` | Update candidate headline, target role, bio | Yes (JWT) |

### 1.1 `POST /auth/register` Payload
```json
{
  "email": "student@university.edu",
  "password": "StudentPass123!",
  "full_name": "Alex Mercer",
  "role": "candidate"
}
```

### 1.2 `POST /auth/login` Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1Ni...",
  "token_type": "bearer",
  "user_id": 2,
  "email": "student@university.edu",
  "role": "candidate"
}
```

## 2. Adaptive Interview & Evaluation Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/interviews` | Launch new configured interview session |
| `GET` | `/interviews/{id}` | Fetch active session & authoritative state |
| `POST` | `/interviews/{id}/answer` | Submit candidate answer turn & trigger evaluation |
| `POST` | `/interviews/{id}/finish` | Terminate interview & generate final report |
| `GET` | `/reports/{id}` | Retrieve final performance report & rubric scores |

### 2.1 `POST /interviews/{id}/answer` Request Payload
```json
{
  "answer_text": "Database indexing uses B-Trees to organize keys hierarchically, reducing disk I/O operations from O(N) to O(log N).",
  "audio_url": null,
  "stt_latency_ms": 0
}
```

### 2.2 `POST /interviews/{id}/answer` Response Payload
```json
{
  "evaluation": {
    "correctness_score": 8.5,
    "relevance_score": 9.0,
    "reasoning_score": 8.0,
    "depth_score": 7.5,
    "communication_score": 8.5,
    "overall_question_score": 8.3,
    "evidence": ["Identified B-Tree node structure", "Mentioned time complexity"],
    "feedback_text": "Excellent explanation of B-Trees. Consider elaborating on write overhead.",
    "confidence_score": 0.95,
    "human_review_required": false
  },
  "next_question": {
    "id": 4,
    "topic": "Relational Databases",
    "subtopic": "Concurrency",
    "difficulty": "hard",
    "question_type": "technical",
    "question_text": "How do isolation levels impact lock contention in concurrent database transactions?",
    "expected_concepts": ["ACID", "Isolation levels", "Phantom reads"],
    "follow_ups": []
  },
  "interview_state": {
    "current_topic": "Relational Databases",
    "difficulty": "hard",
    "time_remaining_seconds": 1640,
    "questions_asked_count": 2,
    "skill_scores": { "Relational Databases": 8.3 },
    "weak_topics": [],
    "strong_topics": ["Relational Databases"],
    "covered_topics": ["Relational Databases"],
    "remaining_topics": ["System Design"],
    "interview_stage": "core"
  },
  "is_completed": false
}
```
