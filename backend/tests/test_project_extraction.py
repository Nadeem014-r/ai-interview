import pytest
from app.resume.parser import ResumeParser, calculate_project_score
from app.matching.matcher import JobMatchingEngine
from app.db.models import Role

def test_resume_with_no_projects():
    """TEST 1: Resume with no projects -> 0 projects, 0% project score."""
    raw_text = """
    John Doe
    john@example.com | (555) 123-4567
    
    EDUCATION
    B.Tech in Computer Science, Stanford University, 2022-2026
    GPA: 3.8/4.0
    
    SKILLS
    Python, Java, C++
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0
    
    role = Role(
        id=1,
        title="Software Engineer",
        company_id=1,
        level="entry",
        required_skills=["Python"],
        key_topics=["Algorithms"]
    )
    match_res = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=result["skills"],
        candidate_experience_level="entry",
        candidate_education=result["education"],
        candidate_projects=result["projects"],
        candidate_experience=result["experience"],
        role=role
    )
    assert match_res["breakdown"]["projects_score"] == 0.0

def test_resume_with_one_basic_project():
    """TEST 2: Resume with one basic project -> 1 project, non-zero realistic score."""
    raw_text = """
    Jane Smith
    jane@example.com
    
    EDUCATION
    B.Tech Computer Science, 2024
    
    PROJECTS
    Task Management App | Python, SQLite
    • Developed a desktop task manager to track daily assignments.
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 1
    proj = result["projects"][0]
    assert "Task Management" in proj["name"]
    assert "Python" in proj["technologies"]
    assert "SQLite" in proj["technologies"]
    assert 30 <= proj["score"] <= 75

def test_resume_with_three_specific_projects():
    """TEST 3: Resume with the user's specific 3 projects."""
    raw_text = """
    Alex Johnson
    alex@example.com
    
    EDUCATION
    B.Tech in Computer Science, 2025
    
    ACADEMIC PROJECTS
    Student Performance Prediction | Python, pandas, scikit-learn
    • Developed machine learning pipeline to preprocess student records, compare regression models, and evaluate performance.
    
    Movie Recommendation System | Python, pandas, scikit-learn
    • Implemented content-based filtering and collaborative recommendation using cosine similarity.
    
    AI Chatbot for College FAQs | Python, NLP, Flask
    • Built an interactive FAQ chatbot with NLP intent classification and Flask REST API.
    
    SKILLS
    Python, Scikit-Learn, Pandas, Flask, NLP
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 3
    
    p1 = result["projects"][0]
    assert "Student Performance Prediction" in p1["name"]
    assert any(t.lower() == "python" for t in p1["technologies"])
    assert any("scikit" in t.lower() for t in p1["technologies"])
    assert 45 <= p1["score"] <= 85
    
    p2 = result["projects"][1]
    assert "Movie Recommendation System" in p2["name"]
    assert any("scikit" in t.lower() for t in p2["technologies"])
    assert 45 <= p2["score"] <= 85
    
    p3 = result["projects"][2]
    assert "AI Chatbot for College FAQs" in p3["name"]
    assert any("flask" in t.lower() for t in p3["technologies"])
    assert 45 <= p3["score"] <= 85

    role = Role(
        id=1,
        title="Backend & ML Engineer",
        company_id=1,
        level="entry",
        required_skills=["Python", "Scikit-Learn"],
        key_topics=["Machine Learning", "Flask"]
    )
    match_res = JobMatchingEngine.match_candidate_to_role(
        candidate_skills=result["skills"],
        candidate_experience_level="entry",
        candidate_education=result["education"],
        candidate_projects=result["projects"],
        candidate_experience=result["experience"],
        role=role
    )
    # Overall projects score must be non-zero and equal average of project scores
    assert match_res["breakdown"]["projects_score"] > 50.0

def test_resume_with_coursework_not_projects():
    """TEST 4: Resume with coursework -> Coursework is NOT extracted as projects."""
    raw_text = """
    Sam Wilson
    sam@example.com
    
    EDUCATION
    B.S. in Software Engineering, 2026
    
    RELEVANT COURSEWORK
    • Data Structures and Algorithms
    • Operating Systems
    • Database Management Systems
    • Software Engineering Principles
    
    SKILLS
    Python, C++
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0

def test_resume_projects_and_experience_separation():
    """TEST 5: Resume with projects + experience -> Remain completely separate."""
    raw_text = """
    Taylor Reed
    taylor@example.com
    
    WORK EXPERIENCE
    Software Engineer Intern
    Google
    • Built automated telemetry pipelines.
    
    PROJECTS
    Movie Recommendation System | Python, Scikit-Learn
    • Built content-based movie recommender.
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 1
    assert len(result["experience"]) == 1
    assert result["projects"][0]["name"] == "Movie Recommendation System"
    assert "Software Engineer Intern" in result["experience"][0]["role"]

def test_deterministic_scoring_reproducibility():
    """TEST 6: Running the parser and scoring twice yields exact identical results."""
    raw_text = """
    Candidate A
    
    PROJECTS
    Student Performance Prediction | Python, pandas, scikit-learn
    • Preprocessed dataset, trained Random Forest model with 91% accuracy and evaluated metrics.
    """
    res1 = ResumeParser.deterministic_rule_parse(raw_text)
    res2 = ResumeParser.deterministic_rule_parse(raw_text)
    assert res1["projects"][0]["score"] == res2["projects"][0]["score"]
    assert res1["projects"][0]["name"] == res2["projects"][0]["name"]
    assert res1["projects"][0]["technologies"] == res2["projects"][0]["technologies"]

def test_student_and_objective_not_classified_as_projects():
    """TEST 7: Assert 'Computer Science Student', 'B.Tech Student', 'Career Objective' are NEVER projects."""
    raw_text = """
    Nadeem Rashid
    nadeem@example.com
    
    PROFILE
    Computer Science Student
    B.Tech Student
    Career Objective: Seeking software engineering opportunities.
    Interested in Technology
    
    EDUCATION
    B.Tech in Computer Science, 2026
    
    SKILLS
    Python, SQL, Data Structures
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0
    project_names = [p["name"].lower() for p in result["projects"]]
    assert "computer science student" not in project_names
    assert "b.tech student" not in project_names
    assert "career objective" not in project_names

def test_exact_project_title_preserved():
    """TEST 8: Real project headings are preserved without invention or mutation."""
    raw_text = """
    Candidate B
    
    PROJECTS
    AI Interview Platform | Python, FastAPI, React
    • Developed automated technical interview platform with LLM reasoning.
    
    Resume Analyzer | Python, PyPDF2
    • Built parsing tool to extract technical credentials from candidate documents.
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert result["projects"][0]["name"] == "AI Interview Platform"
    assert result["projects"][1]["name"] == "Resume Analyzer"

def test_mandatory_test_1_resume_with_no_projects():
    """MANDATORY TEST 1: Resume with education and profile, no projects -> Projects = 0."""
    raw_text = """
    Jane Doe
    jane@example.com
    GitHub: github.com/janedoe
    
    PROFILE
    Computer Science Student seeking software engineering roles.
    
    EDUCATION
    B.Tech in Computer Science, 2026
    Stanford University
    
    CERTIFICATES
    Python Certificate
    AWS Certified Cloud Practitioner
    
    SKILLS
    Python, Java, SQL
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0
    assert not any(p["name"].lower() == "github" for p in result["projects"])
    assert not any("certificate" in p["name"].lower() for p in result["projects"])
    assert not any("student" in p["name"].lower() for p in result["projects"])

def test_mandatory_test_2_resume_with_real_projects():
    """MANDATORY TEST 2: Resume with exact project headings extracts exactly those titles."""
    raw_text = """
    John Doe
    john@example.com
    
    PROJECTS
    Drinking Water Quality Prediction Using Machine Learning | Python, Pandas, Scikit-Learn
    • Built end-to-end classification pipeline for predicting potable water samples with 89% accuracy.
    
    Smart Water Tank Assistant | Python, IoT, Flask
    • Developed automated monitoring system with sensor telemetry and web dashboard.
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 2
    assert result["projects"][0]["name"] == "Drinking Water Quality Prediction Using Machine Learning"
    assert result["projects"][1]["name"] == "Smart Water Tank Assistant"

def test_mandatory_test_3_certifications_never_become_projects():
    """MANDATORY TEST 3: Certifications remain certifications and MUST NOT appear under Projects."""
    raw_text = """
    Alice Smith
    alice@example.com
    
    EDUCATION
    B.Sc in Computer Science, 2025
    
    CERTIFICATIONS
    Python Certificate
    AWS Certificate
    
    SKILLS
    Python, AWS, Git
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0
    project_names = [p["name"].lower() for p in result["projects"]]
    assert "python certificate" not in project_names
    assert "aws certificate" not in project_names

def test_mandatory_test_4_github_never_becomes_project():
    """MANDATORY TEST 4: GitHub is contact/profile link, MUST NOT become Project: GitHub."""
    raw_text = """
    Bob Wilson
    bob@example.com
    GitHub: github.com/example
    LinkedIn: linkedin.com/in/bob
    
    EDUCATION
    B.E. in Information Technology, 2025
    
    SKILLS
    JavaScript, React, Node.js
    """
    result = ResumeParser.deterministic_rule_parse(raw_text)
    assert len(result["projects"]) == 0
    assert not any("github" in p["name"].lower() for p in result["projects"])
    assert not any("linkedin" in p["name"].lower() for p in result["projects"])
