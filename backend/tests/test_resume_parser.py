import pytest
from app.resume.parser import ResumeParser

def test_resume_parser_regex_and_skills():
    sample_text = """
    John Doe
    Email: john.doe@university.edu
    Phone: +1 555-019-2834
    
    Education:
    Bachelor of Technology in Computer Science, 2024
    
    Technical Skills:
    Python, FastAPI, Docker, PostgreSQL, React, Next.js, Redis, Git, Linux
    
    Experience:
    Backend Intern at TechCorp (2 years)
    Developed high throughput microservices using Python and FastAPI.
    """

    data = ResumeParser.deterministic_rule_parse(sample_text)
    
    assert data["explicit_facts"]["email"] == "john.doe@university.edu"
    assert "555-019-2834" in data["explicit_facts"]["phone"]
    assert "Python" in data["skills"]
    assert "FastAPI" in data["skills"]
    assert "Docker" in data["skills"]
    assert "PostgreSQL" in data["skills"]
    assert data["model_inferred"]["estimated_experience_level"] in ["entry", "mid", "senior"]
