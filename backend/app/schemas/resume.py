from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

class ResumeProfileOut(BaseModel):
    id: int
    resume_id: int
    raw_text: str
    explicit_facts: Dict[str, Any]
    model_inferred: Dict[str, Any]
    skills: List[str]
    projects: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    experience: List[Dict[str, Any]]
    technologies: List[str]
    parsed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResumeProfileUpdate(BaseModel):
    explicit_facts: Optional[Dict[str, Any]] = None
    model_inferred: Optional[Dict[str, Any]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    technologies: Optional[List[str]] = None

class ResumeOut(BaseModel):
    id: int
    user_id: int
    filename: str
    file_size: int
    mime_type: str
    created_at: datetime
    resume_profile: Optional[ResumeProfileOut] = None

    model_config = ConfigDict(from_attributes=True)


