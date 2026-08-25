"""Phase 8: Structured Output Schemas & Validation Utilities.

Defines Pydantic schemas for core LLM interactions (evaluations, reports,
questions, resume extraction, research synthesis) and validates structured output.
"""

from typing import List, Dict, Any, Optional, Type, Union
from pydantic import BaseModel, Field, ValidationError
from app.ai.exceptions import AIStructuredOutputError


class EvaluationSchema(BaseModel):
    correctness_score: float = Field(ge=0.0, le=10.0, default=7.0)
    relevance_score: float = Field(ge=0.0, le=10.0, default=7.0)
    reasoning_score: float = Field(ge=0.0, le=10.0, default=7.0)
    depth_score: float = Field(ge=0.0, le=10.0, default=7.0)
    communication_score: float = Field(ge=0.0, le=10.0, default=7.0)
    evidence: List[str] = Field(default_factory=list)
    feedback_text: str = Field(default="")
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    human_review_required: bool = Field(default=False)


class ReportSynthesisSchema(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    difficult_topics: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    executive_summary: str = Field(default="")


class QuestionGenerationSchema(BaseModel):
    question_text: str
    expected_concepts: List[str] = Field(default_factory=list)
    follow_ups: List[str] = Field(default_factory=list)


class ResumeExplicitFactsSchema(BaseModel):
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    education_degrees: List[str] = Field(default_factory=list)
    gpa_or_marks: Optional[str] = None
    verified_companies: List[str] = Field(default_factory=list)


class ResumeModelInferredSchema(BaseModel):
    estimated_experience_level: Optional[str] = None
    primary_technical_domain: Optional[str] = None


class ResumeParsingSchema(BaseModel):
    explicit_facts: ResumeExplicitFactsSchema = Field(default_factory=ResumeExplicitFactsSchema)
    model_inferred: ResumeModelInferredSchema = Field(default_factory=ResumeModelInferredSchema)
    skills: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class ResearchSynthesisSchema(BaseModel):
    description: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    key_topics: List[str] = Field(default_factory=list)
    interview_categories: List[str] = Field(default_factory=list)
    culture_keywords: List[str] = Field(default_factory=list)
    confidence_level: str = Field(default="medium")


def validate_structured_data(
    data: Any,
    schema: Union[Type[BaseModel], Dict[str, Any]],
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate data dictionary against a Pydantic model or required keys schema.
    Raises AIStructuredOutputError if validation fails.
    """
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            instance = schema.model_validate(data)
            return instance.model_dump()
        except ValidationError as e:
            raise AIStructuredOutputError(
                f"Data failed schema validation: {e}",
                schema_errors=e.errors(),
                provider=provider
            ) from e
    elif isinstance(schema, dict):
        # Validate required dictionary keys if provided
        if not isinstance(data, dict):
            raise AIStructuredOutputError(
                f"Expected JSON object (dict), got {type(data).__name__}",
                provider=provider
            )
        missing_keys = [k for k in schema.keys() if k not in data]
        if missing_keys:
            raise AIStructuredOutputError(
                f"Structured output missing required keys: {missing_keys}",
                schema_errors=missing_keys,
                provider=provider
            )
        return data
    else:
        # If schema is None or generic type, return data directly if valid dict
        if not isinstance(data, dict):
            raise AIStructuredOutputError(f"Expected dict, got {type(data).__name__}", provider=provider)
        return data
