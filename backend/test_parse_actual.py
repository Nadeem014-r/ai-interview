import asyncio
import sys
from app.resume.parser import ResumeParser

with open('actual_user_resume_raw.txt', 'r', encoding='utf-8') as f:
    text = f.read()

res = ResumeParser.deterministic_rule_parse(text)
print("=== PARSED PROJECTS COUNT:", len(res["projects"]))
for i, p in enumerate(res["projects"], 1):
    print(f"{i}. Name: {p['name']}")
    print(f"   Tech: {p['technologies']}")
    print(f"   Summary: {p['evidence_summary']}")
    print(f"   Score: {p['score']}")

print("\n=== PARSED EXPERIENCE COUNT:", len(res["experience"]))
for e in res["experience"]:
    print(f"Role: {e.get('role')} | Company: {e.get('company')} | Duration: {e.get('duration')}")

print("\n=== PARSED EDUCATION COUNT:", len(res["education"]))
for ed in res["education"]:
    print(f"Degree: {ed.get('degree')} | Institution: {ed.get('institution')}")

print("\n=== PARSED SKILLS COUNT:", len(res["skills"]))
print(res["skills"])

# Verify assertions
assert len(res["projects"]) == 3, f"Expected 3 projects, got {len(res['projects'])}"
expected_names = [
    "Drinking Water Quality Prediction Using Machine Learning",
    "Smart Water tank Assistant",
    "Desktop voice assistant"
]
for idx, expected in enumerate(expected_names):
    assert res["projects"][idx]["name"] == expected, f"Project {idx+1} mismatch: {res['projects'][idx]['name']} != {expected}"

# Verify forbidden project names
forbidden = [
    "GitHub", "Certificates", "Database Management System-Part 1", "Community Development",
    "Career Essentials in Generative AI", "Ethics in the age of Generative AI", "Wascrap Startup",
    "Lovely Professional University", "Bachelor of Technology", "Computer Science and Engineering",
    "C++", "Python", "Java", "PostgreSQL", "Git", "MS SQL Server", "Implemented a modular voice pipeline"
]
actual_project_names = [p["name"] for p in res["projects"]]
for f_item in forbidden:
    assert f_item not in actual_project_names, f"Forbidden item '{f_item}' found in projects!"

print("\n>>> ALL ASSERTIONS PASSED PERFECTLY! <<<")
