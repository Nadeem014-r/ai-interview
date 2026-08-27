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


# ==========================================
# Phase 1 Regression Tests for Job Matching
# ==========================================

def test_frontend_candidate_favors_frontend_role():
    """Frontend-heavy candidate should score higher on frontend role than on backend/ML role."""
    fe_skills = ["React", "Next.js", "TypeScript", "JavaScript", "CSS"]
    education = [{"degree": "B.Tech in Computer Science"}]
    projects = [{"name": "Portfolio App", "technologies": ["React", "TypeScript"]}]

    fe_role = Role(
        id=101,
        company_id=1,
        title="Frontend Engineer",
        level="Entry / L3",
        required_skills=["React", "TypeScript", "JavaScript", "Next.js"],
        key_topics=["React Architecture", "Web Performance"]
    )
    be_role = Role(
        id=102,
        company_id=1,
        title="Backend Engineer",
        level="Entry / L3",
        required_skills=["Go", "Kubernetes", "gRPC", "PostgreSQL"],
        key_topics=["Distributed Systems", "Concurrency"]
    )
    ml_role = Role(
        id=103,
        company_id=1,
        title="ML Engineer",
        level="Entry / L3",
        required_skills=["Python", "PyTorch", "TensorFlow", "Pandas"],
        key_topics=["Deep Learning", "Model Training"]
    )

    m_fe = JobMatchingEngine.match_candidate_to_role(fe_skills, "entry", education, projects, fe_role)
    m_be = JobMatchingEngine.match_candidate_to_role(fe_skills, "entry", education, projects, be_role)
    m_ml = JobMatchingEngine.match_candidate_to_role(fe_skills, "entry", education, projects, ml_role)

    assert m_fe["overall_score"] > m_be["overall_score"]
    assert m_fe["overall_score"] > m_ml["overall_score"]
    assert m_fe["breakdown"]["skills_score"] == 100.0
    assert m_be["breakdown"]["skills_score"] == 0.0
    assert m_ml["breakdown"]["skills_score"] == 0.0


def test_ml_candidate_favors_ml_role():
    """ML/data-heavy candidate should score higher on ML role than on frontend/DevOps role."""
    ml_skills = ["Python", "PyTorch", "TensorFlow", "Machine Learning", "Pandas", "NumPy"]
    education = [{"degree": "M.S. in Data Science"}]
    projects = [{"name": "Image Classifier", "technologies": ["Python", "PyTorch"]}]

    ml_role = Role(
        id=201,
        company_id=1,
        title="Machine Learning Engineer",
        level="Entry / L3",
        required_skills=["Python", "PyTorch", "TensorFlow", "Machine Learning", "Pandas"],
        key_topics=["Model Optimization", "Deep Learning"]
    )
    fe_role = Role(
        id=202,
        company_id=1,
        title="Frontend UI Developer",
        level="Entry / L3",
        required_skills=["React", "Vue", "Angular", "HTML", "CSS"],
        key_topics=["UI Design", "CSS Grid"]
    )

    m_ml = JobMatchingEngine.match_candidate_to_role(ml_skills, "entry", education, projects, ml_role)
    m_fe = JobMatchingEngine.match_candidate_to_role(ml_skills, "entry", education, projects, fe_role)

    assert m_ml["overall_score"] > m_fe["overall_score"]
    assert m_ml["breakdown"]["skills_score"] == 100.0
    assert m_fe["breakdown"]["skills_score"] == 0.0


def test_unrelated_skills_do_not_receive_full_credit():
    """Unrelated skills should not match role requirements."""
    unrelated_skills = ["Ruby", "PHP", "Photoshop", "SEO"]
    education = [{"degree": "B.A."}]

    role = Role(
        id=301,
        company_id=1,
        title="Systems Engineer",
        level="Entry / L3",
        required_skills=["Rust", "C++", "Linux", "Networking"],
        key_topics=["Operating Systems", "Memory Safety"]
    )

    result = JobMatchingEngine.match_candidate_to_role(unrelated_skills, "entry", education, [], role)
    assert result["breakdown"]["skills_score"] == 0.0
    assert len(result["matched_skills"]) == 0
    assert len(result["missing_skills"]) == 4


def test_deterministic_matching_results():
    """Identical candidate inputs must produce bit-for-bit identical, stable scores across repeated runs."""
    skills = ["Python", "Django", "PostgreSQL", "Docker"]
    education = [{"degree": "B.Tech"}]
    projects = [{"name": "Web App", "technologies": ["Python", "Django"]}]

    role = Role(
        id=401,
        company_id=1,
        title="Backend Developer",
        level="Entry / L3",
        required_skills=["Python", "PostgreSQL", "Docker", "REST APIs"],
        key_topics=["Databases", "API Design"]
    )

    res1 = JobMatchingEngine.match_candidate_to_role(skills, "entry", education, projects, role)
    res2 = JobMatchingEngine.match_candidate_to_role(skills, "entry", education, projects, role)
    res3 = JobMatchingEngine.match_candidate_to_role(skills, "entry", education, projects, role)

    assert res1["overall_score"] == res2["overall_score"] == res3["overall_score"]
    assert res1["breakdown"] == res2["breakdown"] == res3["breakdown"]
    assert res1["matched_skills"] == res2["matched_skills"] == res3["matched_skills"]


def test_matching_does_not_fabricate_skills():
    """Matched skills must strictly be a subset of candidate's actual skills."""
    skills = ["Python", "Flask"]
    role = Role(
        id=501,
        company_id=1,
        title="Senior Cloud Engineer",
        level="Senior",
        required_skills=["Python", "AWS", "Terraform", "Kubernetes", "Golang", "Grafana"],
        key_topics=["Cloud Infrastructure", "Monitoring"]
    )

    result = JobMatchingEngine.match_candidate_to_role(skills, "entry", [], [], role)
    assert set(result["matched_skills"]).issubset({"Python", "Flask"})
    assert "AWS" not in result["matched_skills"]
    assert "Terraform" not in result["matched_skills"]
    assert "Kubernetes" not in result["matched_skills"]
    assert "AWS" in result["missing_skills"]


def test_empty_role_skills_handled_safely():
    """Roles with empty or null required_skills must not receive false 100% skill match score."""
    skills = ["Python", "React", "SQL"]
    empty_role = Role(
        id=601,
        company_id=1,
        title="Generic Role",
        level="Entry / L3",
        required_skills=[],
        key_topics=[]
    )

    result = JobMatchingEngine.match_candidate_to_role(skills, "entry", [], [], empty_role)
    assert result["breakdown"]["skills_score"] == 0.0
    assert result["matched_skills"] == []
    assert result["missing_skills"] == []
