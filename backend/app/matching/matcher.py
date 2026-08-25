from typing import List, Dict, Any, Optional
import re
from app.db.models import Role, Company, ResumeProfile, CandidateProfile

class JobMatchingEngine:
    """
    Modular, deterministic, and explainable Job-Resume matching and scoring engine.
    Computes compatibility across:
    - Skills match (Weight: 50%)
    - Experience level match (Weight: 20%)
    - Education match (Weight: 10%)
    - Projects & Domain match (Weight: 20%)
    """
    
    DEFAULT_WEIGHTS = {
        "skills": 0.50,
        "experience": 0.20,
        "education": 0.10,
        "projects_domain": 0.20
    }

    @classmethod
    def match_candidate_to_role(
        cls,
        candidate_skills: List[str],
        candidate_experience_level: str,
        candidate_education: List[Dict[str, Any]],
        candidate_projects: List[Dict[str, Any]],
        role: Role,
        company: Optional[Company] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        w = weights or cls.DEFAULT_WEIGHTS

        # Normalize skill sets (case-insensitive)
        cand_skills_lower = {s.strip().lower(): s for s in candidate_skills if s}
        req_skills = role.required_skills or []
        req_skills_lower = {s.strip().lower(): s for s in req_skills if s}

        # 1. Skills Matching
        matched_skills = []
        missing_skills = []
        for s_lower, orig_s in req_skills_lower.items():
            if s_lower in cand_skills_lower or any(s_lower in cs or cs in s_lower for cs in cand_skills_lower):
                matched_skills.append(orig_s)
            else:
                missing_skills.append(orig_s)

        if req_skills:
            skills_score = (len(matched_skills) / len(req_skills)) * 100.0
        else:
            skills_score = 100.0 if candidate_skills else 50.0

        # 2. Experience Level Matching
        role_level = (role.level or "").lower()
        cand_level = (candidate_experience_level or "entry").lower()
        
        if "senior" in role_level or "l5" in role_level:
            exp_score = 100.0 if "senior" in cand_level else (70.0 if "mid" in cand_level else 40.0)
        elif "mid" in role_level or "l4" in role_level:
            exp_score = 100.0 if ("mid" in cand_level or "senior" in cand_level) else 75.0
        else: # entry / l3 / graduate
            exp_score = 100.0

        # 3. Education Matching
        edu_score = 80.0 # baseline
        if candidate_education:
            edu_str = " ".join(str(e.get("degree", "")) for e in candidate_education).lower()
            if any(term in edu_str for term in ["b.tech", "btech", "computer science", "b.e", "m.tech", "m.s", "bachelor", "master"]):
                edu_score = 100.0
            else:
                edu_score = 70.0

        # 4. Projects & Domain Keywords Matching
        key_topics = role.key_topics or []
        project_techs = []
        for p in candidate_projects:
            for t in p.get("technologies", []):
                project_techs.append(t.lower())

        matched_topics = 0
        for topic in key_topics:
            topic_lower = topic.lower()
            if any(topic_lower in pt or pt in topic_lower for pt in project_techs) or any(topic_lower in cs for cs in cand_skills_lower):
                matched_topics += 1

        if key_topics:
            projects_score = (matched_topics / len(key_topics)) * 100.0
        else:
            projects_score = 80.0 if candidate_projects else 50.0

        # Weighted Total Score
        overall_score = round(
            (skills_score * w["skills"]) +
            (exp_score * w["experience"]) +
            (edu_score * w["education"]) +
            (projects_score * w["projects_domain"]),
            1
        )
        overall_score = min(100.0, max(0.0, overall_score))

        # Generate Strengths, Weaknesses & Recommendations
        strengths = []
        if matched_skills:
            strengths.append(f"Strong alignment with {len(matched_skills)} core technical skills: {', '.join(matched_skills[:4])}.")
        if exp_score >= 80:
            strengths.append(f"Target experience tier ({candidate_experience_level.capitalize()}) matches role expectation ({role.level}).")
        if candidate_projects:
            strengths.append(f"Demonstrated practical project work relevant to {role.title}.")

        weaknesses = []
        if missing_skills:
            weaknesses.append(f"Missing {len(missing_skills)} expected job requirements: {', '.join(missing_skills)}.")
        if projects_score < 70:
            weaknesses.append("Project portfolio has limited direct overlap with role's key architectural topics.")

        recommendations = []
        if missing_skills:
            recommendations.append(f"Build mini-projects focusing on: {', '.join(missing_skills[:3])}.")
        if key_topics:
            recommendations.append(f"Prepare technical interview deep-dives on: {', '.join(key_topics[:3])}.")

        return {
            "role_id": role.id,
            "role_title": role.title,
            "company_id": role.company_id,
            "company_name": company.name if company else "Target Company",
            "role_level": role.level,
            "overall_score": overall_score,
            "breakdown": {
                "skills_score": round(skills_score, 1),
                "experience_score": round(exp_score, 1),
                "education_score": round(edu_score, 1),
                "projects_score": round(projects_score, 1)
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "strengths": strengths or ["Basic candidate foundational profile ready."],
            "weaknesses": weaknesses or ["No significant technical blockers identified."],
            "recommendations": recommendations or ["Review standard technical fundamentals and data structures."]
        }
