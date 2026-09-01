"""Pydantic v2 models for the Skill Taxonomy & JD Gap Delta engine.

Defines strict categorical buckets for resume skill classification and
structured output models for JD alignment scoring.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SkillTaxonomy(BaseModel):
    """Five-bucket categorical skill taxonomy extracted from a resume."""

    core_technical_skills: List[str] = Field(
        default_factory=list,
        description=(
            "Pure technical competencies: programming languages, core CS concepts, "
            "ML/AI paradigms, protocols, distributed systems. "
            "Examples: Python, PyTorch, RAG, WebSockets, Transformers, Distributed Systems."
        )
    )
    frameworks_and_libraries: List[str] = Field(
        default_factory=list,
        description=(
            "Application frameworks, ML libraries, and runtime environments. "
            "Examples: FastAPI, React, Next.js, LangChain, HuggingFace, Scikit-Learn, TensorFlow."
        )
    )
    developer_tools: List[str] = Field(
        default_factory=list,
        description=(
            "Infrastructure, DevOps, and build tooling. "
            "Examples: Docker, Kubernetes, CI/CD, Terraform. "
            "EXCLUDE: GitHub, GitLab (platform UIs), VS Code, PyCharm, IntelliJ, "
            "Slack, Jira, Confluence, Trello, Notion, Postman as standalone skills."
        )
    )
    domain_knowledge: List[str] = Field(
        default_factory=list,
        description=(
            "Applied technical domains and specializations. "
            "Examples: NLP, Computer Vision, MLOps, Quantitative Finance, "
            "Cybersecurity, Embedded Systems, Data Engineering."
        )
    )
    soft_skills_and_noise: List[str] = Field(
        default_factory=list,
        description=(
            "Non-technical soft skills and tool-noise items excluded from scoring. "
            "Examples: Agile, Scrum, Teamwork, Communication, Leadership, "
            "GitHub (as a collaboration platform), VS Code, Postman."
        )
    )


class SkillTaxonomyResult(BaseModel):
    """Full enriched resume profile with categorical taxonomy overlay."""

    taxonomy: SkillTaxonomy
    raw_skills: List[str] = Field(default_factory=list)
    evaluation_skills: List[str] = Field(
        default_factory=list,
        description=(
            "Deduplicated union of core_technical_skills + frameworks_and_libraries + "
            "domain_knowledge — the only buckets used for interview evaluation."
        )
    )
    noise_filtered: List[str] = Field(default_factory=list)
    taxonomy_generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = "taxonomy_v1"


class TaxonomyMatchResult(BaseModel):
    """Result of matching a candidate's taxonomy against a flat JD skill list."""

    match_percentage: float = Field(ge=0.0, le=100.0)
    matching_strengths: List[str] = Field(default_factory=list)
    partial_matches: List[str] = Field(default_factory=list)


class SkillDeltaResult(BaseModel):
    """Complete skill gap analysis between a candidate and a live job description."""

    job_id: Optional[int] = None
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    match_percentage: float = Field(ge=0.0, le=100.0)
    matching_strengths: List[str] = Field(default_factory=list)
    critical_gaps: List[str] = Field(
        default_factory=list,
        description="JD-required skills absent from candidate core_technical + frameworks buckets."
    )
    emerging_skill_gaps: List[str] = Field(
        default_factory=list,
        description="Skills recently added to JD since last cache snapshot."
    )
    nice_to_have_gaps: List[str] = Field(default_factory=list)
    noise_discarded: List[str] = Field(default_factory=list)
    jd_scraped_at: Optional[datetime] = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapingResult(BaseModel):
    """Raw output from the JD scraping service."""

    company_slug: str
    role_slug: str
    company_name: str
    role_title: str
    raw_jd_text: str
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    jd_url: Optional[str] = None
    source: str = "jina_reader"
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    cached: bool = False
