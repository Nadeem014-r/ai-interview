import pytest
from app.matching.matcher import JobMatchingEngine
from app.db.models import Role, Company

def test_job_matching_full_score():
    candidate_skills = ["python", "fastapi", "data structures", "relational databases", "sql"]
    candidate_experience_level = "entry"
    candidate_education = [{"degree": "B.Tech in Computer Science"}]
    candidate_projects = [{"name": "Distributed Cache", "technologies": ["Python", "Data Structures"]}]

    company = Company(id=1, name="Google", slug="google")
    role = Role(
        id=1,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "FastAPI", "Data Structures"],
        key_topics=["Data Structures", "Relational Databases"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level=candidate_experience_level,
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        role=role,
        company=company
    )

    assert result["role_id"] == 1
    assert result["company_name"] == "Google"
    assert result["overall_score"] >= 80.0
    assert "Python" in result["matched_skills"]
    assert len(result["missing_skills"]) == 0
    assert len(result["strengths"]) > 0

def test_job_matching_missing_skills():
    candidate_skills = ["html", "css", "javascript"]
    candidate_experience_level = "entry"
    candidate_education = [{"degree": "B.Sc"}]
    candidate_projects = []

    company = Company(id=2, name="Amazon", slug="amazon")
    role = Role(
        id=2,
        company_id=2,
        title="Cloud Architect",
        level="Senior",
        required_skills=["Kubernetes", "Terraform", "Go", "AWS"],
        key_topics=["Distributed Systems", "Cloud Security"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level=candidate_experience_level,
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        role=role,
        company=company
    )

    assert result["overall_score"] < 60.0
    assert len(result["missing_skills"]) >= 3
    assert len(result["recommendations"]) > 0
