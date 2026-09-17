from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long.")
    full_name: str = Field(..., min_length=1, max_length=150)
    role: Optional[str] = "candidate"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    headline: Optional[str] = None
    target_role: Optional[str] = None
    experience_level: Optional[str] = "entry"
    # Nobody has a negative amount of experience. The field used to be absent
    # from this model entirely, so a PUT carrying -0.5 was accepted with a 200
    # and the value silently dropped; it is now declared and constrained, so an
    # impossible value is rejected outright rather than quietly rewritten to 0.
    # Half-years stay valid, which is why this is a float and not an int.
    experience_years: Optional[float] = Field(default=None, ge=0)
    bio: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    graduation_year: Optional[int] = None
    skills: Optional[List[str]] = []
    experience: Optional[List[Dict[str, Any]]] = []
    projects: Optional[List[Dict[str, Any]]] = []
    certifications: Optional[List[str]] = []
    preferences: Optional[Dict[str, Any]] = {}
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None

class ProfileOut(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    headline: Optional[str] = None
    target_role: Optional[str] = None
    experience_level: str = "entry"
    experience_years: Optional[float] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    graduation_year: Optional[int] = None
    skills: List[str] = []
    experience: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    certifications: List[str] = []
    preferences: Dict[str, Any] = {}
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


