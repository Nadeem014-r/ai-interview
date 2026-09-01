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
    assert result["overall_score"] >= 70.0
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


def test_first_year_no_skills_projects_or_experience():
    """First-year student with no skills, no projects, and no experience must receive 0% across technical subscores and 0% overall."""
    education = [{"degree": "B.Tech in Computer Science", "institution": "University"}]
    skills = []
    projects = []
    experience = []

    role = Role(
        id=701,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "FastAPI", "SQL", "Docker"],
        key_topics=["API Design", "Databases"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=skills,
        candidate_experience_level="entry",
        candidate_education=education,
        candidate_projects=projects,
        candidate_experience=experience,
        role=role
    )

    assert result["breakdown"]["skills_score"] == 0.0
    assert result["breakdown"]["projects_score"] == 0.0
    assert result["breakdown"]["experience_score"] == 0.0
    assert result["overall_score"] == 0.0
    assert len(result["matched_skills"]) == 0
    assert len(result["missing_skills"]) == 4


def test_candidate_with_experience_and_projects_increases_score():
    """Candidate with actual skills, projects, and experience must receive positive scores reflecting evidence."""
    skills = ["Python", "FastAPI", "SQL"]
    projects = [{"name": "API Service", "technologies": ["Python", "FastAPI"]}]
    experience = [{"title": "Software Intern", "company": "Acme Corp"}]
    education = [{"degree": "B.Tech"}]

    role = Role(
        id=702,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "FastAPI", "SQL", "Docker"],
        key_topics=["API Design", "Databases"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=skills,
        candidate_experience_level="entry",
        candidate_education=education,
        candidate_projects=projects,
        candidate_experience=experience,
        role=role
    )

    assert result["breakdown"]["skills_score"] == 75.0
    assert result["breakdown"]["experience_score"] == 50.0
    assert result["breakdown"]["education_score"] == 100.0
    assert result["overall_score"] > 50.0

def test_exact_jd_matching_and_clean_you_have_section():
    """Verify that 'You have' does not contain degree strings as skills and 'Missing' contains all absent JD skills."""
    candidate_skills = ["Python", "SQL", "Data Structures", "Git"]
    candidate_projects = [{"name": "Student Performance Prediction", "technologies": ["Python", "scikit-learn"]}]
    candidate_education = [{"degree": "B.Tech Computer Science"}]

    role = Role(
        id=801,
        company_id=1,
        title="Backend Software Engineer",
        level="Entry / L3",
        required_skills=["Java", "SQL", "Spring Boot", "REST APIs", "AWS", "Docker", "Data Structures", "System Design"],
        key_topics=["Data Structures", "System Design"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level="entry",
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        role=role
    )

    # Matched skills
    assert "SQL" in result["matched_skills"]
    assert "Data Structures" in result["matched_skills"]
    assert "Java" not in result["matched_skills"]
    assert "Python" not in result["matched_skills"]  # Python was in candidate resume but not required by this specific JD

    # Missing skills contains all unfulfilled requirements
    for expected_missing in ["Java", "Spring Boot", "REST APIs", "AWS", "Docker", "System Design"]:
        assert expected_missing in result["missing_skills"]
        assert expected_missing in result["what_you_are_missing"]

    # "You have" contains matched skills and verified project, but NOT "B.Tech" as a skill
    assert "SQL" in result["what_you_have"]
    assert "Data Structures" in result["what_you_have"]
    assert "Project: Student Performance Prediction" in result["what_you_have"]
    assert "B.Tech" not in result["what_you_have"]
    assert "B.Tech Computer Science" not in result["what_you_have"]
    assert not any("student" in str(item).lower() and "project:" not in str(item).lower() for item in result["what_you_have"])

def test_mandatory_test_5_and_7_startup_experience_does_not_become_100_percent():
    """MANDATORY TEST 5 & 7: Startup / single early experience yields proportionate score, NOT 100%."""
    candidate_skills = ["Python", "Flask", "SQL"]
    candidate_experience = [{"role": "Wascrap Startup", "company": "Wascrap", "duration": "Jun 2024 – Present"}]
    candidate_projects = [{"name": "Smart Water Tank Assistant", "technologies": ["Python", "Flask"]}]
    candidate_education = [{"degree": "B.Tech Computer Science"}]

    role = Role(
        id=901,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "Flask", "SQL", "Docker", "Data Structures"],
        key_topics=["API Design"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level="entry",
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        candidate_experience=candidate_experience,
        role=role
    )

    # Experience readiness MUST NOT be 100% for 1 early startup role
    exp_score = result["breakdown"]["experience_score"]
    assert exp_score < 100.0
    assert exp_score == 50.0

def test_mandatory_test_6_no_experience_scores_zero_percent():
    """MANDATORY TEST 6: Candidate with no experience receives 0% experience score."""
    candidate_skills = ["Python", "SQL"]
    candidate_experience = []
    candidate_projects = [{"name": "Student Performance Prediction", "technologies": ["Python"]}]
    candidate_education = [{"degree": "B.Tech"}]

    role = Role(
        id=902,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Python", "SQL"],
        key_topics=["Databases"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level="entry",
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        candidate_experience=candidate_experience,
        role=role
    )

    assert result["breakdown"]["experience_score"] == 0.0

def test_mandatory_test_8_no_technical_evidence_scores_low_across_categories():
    """MANDATORY TEST 8: Candidate with essentially no technical skills -> scores remain appropriately low/zero."""
    candidate_skills = []
    candidate_experience = []
    candidate_projects = []
    candidate_education = []

    role = Role(
        id=903,
        company_id=1,
        title="Software Engineer (Backend)",
        level="Entry / L3",
        required_skills=["Java", "Spring Boot", "AWS", "Kubernetes", "PostgreSQL"],
        key_topics=["Distributed Systems"]
    )

    result = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=candidate_skills,
        candidate_experience_level="entry",
        candidate_education=candidate_education,
        candidate_projects=candidate_projects,
        candidate_experience=candidate_experience,
        role=role
    )

    assert result["breakdown"]["skills_score"] == 0.0
    assert result["breakdown"]["projects_score"] == 0.0
    assert result["breakdown"]["experience_score"] == 0.0
    assert result["breakdown"]["education_score"] == 0.0
    assert result["overall_score"] == 0.0

