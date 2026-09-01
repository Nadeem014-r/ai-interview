from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class RoleOut(BaseModel):
    id: int
    company_id: int
    title: str
    level: str
    description: Optional[str]
    required_skills: List[str]
    key_topics: List[str]
    interview_categories: List[str]

    class Config:
        from_attributes = True

class CompanyOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    website: Optional[str]
    target_roles: List[str]
    culture_keywords: List[str]
    roles: List[RoleOut] = []

    class Config:
        from_attributes = True

class QuestionOut(BaseModel):
    id: int
    topic: str
    subtopic: Optional[str]
    difficulty: str
    question_type: str
    question_text: str
    expected_concepts: List[str]
    follow_ups: List[str]

    class Config:
        from_attributes = True

class InterviewCreate(BaseModel):
    company_id: int
    role_id: int
    mode: str = "text" # text, audio, video
    interview_type: Optional[str] = "technical" # technical, hr, behavioral, role_specific, mixed
    duration_minutes: int = 30 # 10, 15, 30, 45, 60
    target_level: str = "entry"

class InterviewStateOut(BaseModel):
    current_topic: Optional[str]
    difficulty: str
    time_remaining_seconds: int
    questions_asked_count: int
    current_question_id: Optional[int] = None
    skill_scores: Dict[str, float]
    weak_topics: List[str]
    strong_topics: List[str]
    covered_topics: List[str]
    remaining_topics: List[str]
    interview_stage: str

    class Config:
        from_attributes = True

class AnswerItemOut(BaseModel):
    id: int
    question_id: int
    question_text: Optional[str] = None
    candidate_answer_text: str
    created_at: datetime
    evaluation: Optional[Dict[str, Any]] = None

class InterviewOut(BaseModel):
    id: int
    candidate_id: int
    company_id: int
    role_id: int
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    mode: str
    interview_type: str = "technical"
    duration_minutes: int
    target_level: str
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    state: Optional[InterviewStateOut] = None
    current_question: Optional[QuestionOut] = None
    answers: List[AnswerItemOut] = []

    class Config:
        from_attributes = True


class CandidateAnswerSubmit(BaseModel):
    answer_text: str
    audio_url: Optional[str] = None
    stt_latency_ms: Optional[int] = 0

class AnswerTurnResponse(BaseModel):
    evaluation: Dict[str, Any]
    next_question: Optional[QuestionOut] = None
    interview_state: InterviewStateOut
    is_completed: bool
    closing_message: Optional[str] = None
    termination_reason: Optional[str] = None


class EvaluationOut(BaseModel):
    id: int
    answer_id: int
    correctness_score: float
    relevance_score: float
    reasoning_score: float
    depth_score: float
    communication_score: float
    overall_question_score: float
    evidence: List[str]
    feedback_text: Optional[str]
    confidence_score: float
    human_review_required: bool

    class Config:
        from_attributes = True

class ReportOut(BaseModel):
    id: int
    interview_id: int
    overall_score: float
    topic_scores: Dict[str, float]
    rubric_scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    difficult_topics: List[str]
    recommendations: List[str]
    executive_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ResearchCompanyRequest(BaseModel):
    company_name: str
    role_title: str
    source_url: Optional[str] = None

class VoiceSynthesizeRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "default"
