from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="candidate", nullable=False) # candidate, placement_staff, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate_profile = relationship("CandidateProfile", back_populates="user", uselist=False)
    resumes = relationship("Resume", back_populates="user")
    interviews = relationship("Interview", back_populates="candidate")

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    headline = Column(String, nullable=True)
    target_role = Column(String, nullable=True)
    experience_level = Column(String, default="entry") # entry, mid, senior
    bio = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    university = Column(String, nullable=True)
    degree = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    graduation_year = Column(Integer, nullable=True)
    skills = Column(JSON, default=list)
    experience = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    preferences = Column(JSON, default=dict)
    github_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="candidate_profile")

class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="resumes")
    resume_profile = relationship("ResumeProfile", back_populates="resume", uselist=False)

class ResumeProfile(Base):
    __tablename__ = "resume_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), unique=True, nullable=False)
    raw_text = Column(Text, nullable=False)
    explicit_facts = Column(JSON, default=dict)
    model_inferred = Column(JSON, default=dict)
    skills = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    education = Column(JSON, default=list)
    experience = Column(JSON, default=list)
    technologies = Column(JSON, default=list)
    parsed_at = Column(DateTime, default=datetime.utcnow)

    resume = relationship("Resume", back_populates="resume_profile")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    target_roles = Column(JSON, default=list)
    culture_keywords = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    roles = relationship("Role", back_populates="company")
    sources = relationship("Source", back_populates="company")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String, index=True, nullable=False)
    level = Column(String, default="L3/Entry", nullable=False)
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, default=list)
    key_topics = Column(JSON, default=list)
    interview_categories = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="roles")
    questions = relationship("Question", back_populates="role")

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    source_type = Column(String, nullable=False) # career_page, job_desc, tech_blog, candidate_exp
    source_url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    trust_level = Column(String, default="trusted") # official_trusted, public_experience
    fetched_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="sources")
    documents = relationship("Document", back_populates="source")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_json = Column(JSON, default=list) # Array float embeddings stored for fallback/pgvector compatibility

    document = relationship("Document", back_populates="chunks")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    topic = Column(String, index=True, nullable=False)
    subtopic = Column(String, nullable=True)
    difficulty = Column(String, default="medium", nullable=False) # easy, medium, hard
    question_type = Column(String, default="technical", nullable=False) # technical, conceptual, behavioral, hr, resume, coding
    question_text = Column(Text, nullable=False)
    expected_concepts = Column(JSON, default=list)
    evaluation_criteria = Column(JSON, default=dict)
    follow_ups = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="questions")

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    mode = Column(String, default="text", nullable=False) # text, audio, video
    interview_type = Column(String, default="technical", nullable=False) # technical, hr, behavioral, role_specific, mixed
    duration_minutes = Column(Integer, default=30, nullable=False)
    target_level = Column(String, default="entry", nullable=False)
    status = Column(String, default="configured", nullable=False) # configured, in_progress, completed, terminated
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("User", back_populates="interviews")
    company = relationship("Company")
    role = relationship("Role")
    state = relationship("InterviewState", back_populates="interview", uselist=False)
    answers = relationship("Answer", back_populates="interview")
    report = relationship("Report", back_populates="interview", uselist=False)


class InterviewState(Base):
    __tablename__ = "interview_states"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), unique=True, nullable=False)
    current_topic = Column(String, nullable=True)
    difficulty = Column(String, default="medium", nullable=False)
    time_remaining_seconds = Column(Integer, nullable=False)
    questions_asked_count = Column(Integer, default=0, nullable=False)
    topic_question_counts = Column(JSON, default=dict)
    current_question_id = Column(Integer, nullable=True)
    skill_scores = Column(JSON, default=dict)
    weak_topics = Column(JSON, default=list)
    strong_topics = Column(JSON, default=list)
    covered_topics = Column(JSON, default=list)
    remaining_topics = Column(JSON, default=list)
    interview_stage = Column(String, default="intro", nullable=False) # intro, core, deep_dive, wrapup
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interview = relationship("Interview", back_populates="state")

class Answer(Base):
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    candidate_answer_text = Column(Text, nullable=False)
    audio_url = Column(String, nullable=True)
    stt_latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="answers")
    question = relationship("Question")
    evaluation = relationship("Evaluation", back_populates="answer", uselist=False)

class Evaluation(Base):
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    answer_id = Column(Integer, ForeignKey("answers.id"), unique=True, nullable=False)
    correctness_score = Column(Float, default=0.0)
    relevance_score = Column(Float, default=0.0)
    reasoning_score = Column(Float, default=0.0)
    depth_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)
    overall_question_score = Column(Float, default=0.0)
    evidence = Column(JSON, default=list)
    feedback_text = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)
    human_review_required = Column(Boolean, default=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    answer = relationship("Answer", back_populates="evaluation")

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), unique=True, nullable=False)
    overall_score = Column(Float, default=0.0)
    topic_scores = Column(JSON, default=dict)
    rubric_scores = Column(JSON, default=dict)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    difficult_topics = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    executive_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="report")

class UsageMetric(Base):
    __tablename__ = "usage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    provider = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    call_type = Column(String, nullable=False) # llm, embedding, stt, tts
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    audio_duration_sec = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Consent(Base):
    __tablename__ = "consents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consent_type = Column(String, nullable=False) # recording, data_processing
    granted = Column(Boolean, default=True)
    granted_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource = Column(String, nullable=False)
    details_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)
