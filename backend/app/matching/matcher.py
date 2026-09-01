from typing import List, Dict, Any, Optional
import re
from app.db.models import Role, Company, ResumeProfile, CandidateProfile
from app.resume.parser import CANONICAL_SKILL_MAP

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
    def _is_skill_matched(cls, req_skill_lower: str, req_canon_lower: str, cand_skills_map: Dict[str, str]) -> bool:
        """
        Determines if a role requirement matches candidate skills safely.
        Avoids false positives from single/short letter substrings while supporting
        canonical aliases and multi-word semantic variations.
        """
        # Exact raw or canonical match
        if req_skill_lower in cand_skills_map or req_canon_lower in cand_skills_map:
            return True

        # Word boundary / semantic prefix match for longer multi-word skills
        for c_key in cand_skills_map.keys():
            # Exact equality
            if req_skill_lower == c_key or req_canon_lower == c_key:
                return True
            
            # Substring matching only for meaningful term lengths (>= 4 chars) with word boundaries
            if len(req_skill_lower) >= 4 and len(c_key) >= 4:
                if (
                    re.search(r'\b' + re.escape(req_skill_lower) + r'\b', c_key)
                    or re.search(r'\b' + re.escape(c_key) + r'\b', req_skill_lower)
                    or (req_skill_lower in c_key and len(req_skill_lower) >= 5)
                    or (c_key in req_skill_lower and len(c_key) >= 5)
                ):
                    return True

        return False

    @classmethod
    def match_candidate_to_role(
        cls,
        candidate_skills: List[str],
        candidate_experience_level: str,
        candidate_education: List[Dict[str, Any]],
        candidate_projects: List[Dict[str, Any]],
        role: Optional[Role] = None,
        company: Optional[Company] = None,
        weights: Optional[Dict[str, float]] = None,
        candidate_experience: Optional[List[Dict[str, Any]]] = None,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        w = weights or cls.DEFAULT_WEIGHTS

        # Positional compatibility handling
        if role is None and args:
            role = args[0]
        if company is None and len(args) > 1:
            company = args[1]
        if "candidate_experience" in kwargs and candidate_experience is None:
            candidate_experience = kwargs["candidate_experience"]
        if "role" in kwargs and role is None:
            role = kwargs["role"]
        if "company" in kwargs and company is None:
            company = kwargs["company"]
        if "weights" in kwargs and weights is None:
            w = kwargs["weights"]

        # Normalize candidate skill sets (case-insensitive & canonical)
        cand_skills_map: Dict[str, str] = {}
        for s in candidate_skills:
            if s and isinstance(s, str):
                s_clean = s.strip()
                if s_clean:
                    s_lower = s_clean.lower()
                    canon = CANONICAL_SKILL_MAP.get(s_lower, s_clean)
                    cand_skills_map[s_lower] = s_clean
                    cand_skills_map[canon.lower()] = canon

        req_skills = role.required_skills or [] if role else []
        req_clean_list = [s.strip() for s in req_skills if s and isinstance(s, str) and s.strip()]

        # 1. Skills Matching (0% if no matched skills or no skills present)
        matched_skills: List[str] = []
        missing_skills: List[str] = []

        for orig_s in req_clean_list:
            s_lower = orig_s.lower()
            s_canon_lower = CANONICAL_SKILL_MAP.get(s_lower, orig_s).lower()

            if cls._is_skill_matched(s_lower, s_canon_lower, cand_skills_map):
                matched_skills.append(orig_s)
            else:
                missing_skills.append(orig_s)

        if req_clean_list:
            raw_skills_score = (len(matched_skills) / len(req_clean_list)) * 100.0
            # Bug Fix 4: cap static keyword-only score at 85 %; the remaining
            # headroom must be earned through live interview performance.
            skills_score = min(raw_skills_score, 85.0)
        else:
            skills_score = 0.0

        # 2. Experience Level Matching
        # 2. Experience Level Matching
        # Must be based strictly on actual professional experience evidence
        if candidate_experience and len(candidate_experience) > 0:
            num_exp = len(candidate_experience)
            role_level = (role.level or "").lower() if role else ""
            cand_level = (candidate_experience_level or "entry").lower()

            has_senior_exp = any(
                isinstance(e, dict) and any(kw in (e.get("role") or "").lower() for kw in ["senior", "lead", "principal", "architect"])
                for e in candidate_experience
            ) or "senior" in cand_level

            has_mid_exp = any(
                isinstance(e, dict) and any(kw in (e.get("role") or "").lower() for kw in ["software engineer", "developer", "full stack", "backend", "frontend", "engineer"])
                and not any(kw in (e.get("role") or "").lower() for kw in ["intern", "trainee", "student"])
                for e in candidate_experience
            ) or "mid" in cand_level

            if "senior" in role_level or "l5" in role_level:
                if has_senior_exp and num_exp >= 3:
                    exp_score = 90.0
                elif has_senior_exp or (has_mid_exp and num_exp >= 2):
                    exp_score = 70.0
                elif num_exp >= 2:
                    exp_score = 40.0
                else:  # 1 entry or current startup involvement / internship
                    exp_score = 20.0
            elif "mid" in role_level or "l4" in role_level:
                if has_senior_exp or (has_mid_exp and num_exp >= 2):
                    exp_score = 90.0
                elif has_mid_exp or num_exp >= 2:
                    exp_score = 65.0
                else:  # 1 entry or current startup involvement / internship
                    exp_score = 35.0
            else:  # entry / l3 / graduate role
                if has_senior_exp or (has_mid_exp and num_exp >= 2):
                    exp_score = 90.0
                elif num_exp >= 2:
                    exp_score = 75.0
                else:  # 1 limited/current experience entry (e.g. startup involvement or single internship)
                    exp_score = 50.0
        else:
            exp_score = 0.0

        # 3. Education Matching
        if candidate_education and len(candidate_education) > 0:
            edu_str = " ".join(str(e.get("degree", "")) for e in candidate_education if isinstance(e, dict)).lower()
            if any(term in edu_str for term in ["b.tech", "btech", "computer science", "b.e", "m.tech", "m.s", "bachelor", "master"]):
                edu_score = 100.0
            else:
                edu_score = 70.0
        else:
            edu_score = 0.0

        # 4. Projects Evidence Scoring (0% if no projects present)
        from app.resume.parser import calculate_project_score
        key_topics = role.key_topics or [] if role else []
        has_projects = bool(candidate_projects and len(candidate_projects) > 0)
        if not has_projects:
            projects_score = 0.0
        else:
            proj_scores: List[float] = []
            project_techs: List[str] = []
            for p in candidate_projects:
                if isinstance(p, dict):
                    p_name = p.get("name") or p.get("title") or ""
                    p_techs = p.get("technologies") or []
                    p_desc = p.get("evidence_summary") or p.get("description") or ""
                    for t in p_techs:
                        if t and isinstance(t, str):
                            project_techs.append(t.lower())
                    if p_name:
                        project_techs.append(p_name.lower())

                    if p.get("score") is not None:
                        proj_scores.append(float(p["score"]))
                    else:
                        s = calculate_project_score(p_name, p_techs, p_desc)
                        proj_scores.append(float(s))
                elif isinstance(p, str):
                    project_techs.append(p.lower())
                    proj_scores.append(50.0)

            base_proj_score = sum(proj_scores) / len(proj_scores) if proj_scores else 0.0

            matched_topics = 0
            for topic in key_topics:
                topic_lower = topic.lower()
                topic_canon = CANONICAL_SKILL_MAP.get(topic_lower, topic).lower()
                if (
                    any(topic_lower in pt or pt in topic_lower for pt in project_techs)
                    or topic_lower in cand_skills_map
                    or topic_canon in cand_skills_map
                    or any(topic_lower in cs or cs in topic_lower for cs in cand_skills_map if len(cs) >= 4)
                ):
                    matched_topics += 1

            if key_topics:
                topic_ratio = matched_topics / len(key_topics)
                projects_score = (base_proj_score * 0.5) + (topic_ratio * 100.0 * 0.5)
            else:
                projects_score = base_proj_score

            projects_score = round(min(100.0, max(0.0, projects_score)), 1)

        # Overall Compatibility Score
        # If candidate has NO skills, NO projects, and NO experience, overall alignment is 0.0
        if skills_score == 0.0 and projects_score == 0.0 and exp_score == 0.0:
            overall_score = 0.0
        else:
            overall_score = round(
                (skills_score * w["skills"]) +
                (exp_score * w["experience"]) +
                (edu_score * w["education"]) +
                (projects_score * w["projects_domain"]),
                1
            )
            overall_score = min(100.0, max(0.0, overall_score))

        # Identify "What You Have" vs "What You're Missing" based on real evidence
        from app.resume.parser import is_valid_project_name

        what_you_have: List[str] = []
        for s in matched_skills:
            if s not in what_you_have:
                what_you_have.append(s)

        if candidate_projects:
            for p in candidate_projects[:2]:
                title = p.get("title") or p.get("name") if isinstance(p, dict) else str(p)
                if title and is_valid_project_name(title):
                    proj_label = f"Project: {title}"
                    if proj_label not in what_you_have:
                        what_you_have.append(proj_label)

        if candidate_experience:
            for e in candidate_experience[:2]:
                title = e.get("role") or e.get("title") if isinstance(e, dict) else str(e)
                if title:
                    exp_label = f"Experience: {title}"
                    if exp_label not in what_you_have:
                        what_you_have.append(exp_label)

        what_you_are_missing: List[str] = []
        for s in missing_skills:
            if s not in what_you_are_missing:
                what_you_are_missing.append(s)
        if exp_score == 0.0 and role and ("mid" in (role.level or "").lower() or "senior" in (role.level or "").lower()):
            what_you_are_missing.append(f"Required experience ({role.level})")

        # Soft, intelligent eligibility evaluation
        # Student / new grad with skills OR projects is 100% eligible
        # Ineligible ONLY if candidate has 0 skills, 0 projects, and 0 experience
        has_evidence = bool(
            (candidate_skills and len(candidate_skills) > 0)
            or (candidate_projects and len(candidate_projects) > 0)
            or (candidate_experience and len(candidate_experience) > 0)
            or (matched_skills and len(matched_skills) > 0)
        )
        is_eligible = has_evidence
        eligibility_reason = None if is_eligible else "Your profile needs a little more information. To create a meaningful role-specific interview, please add some technical skills, projects, or relevant experience and try again."

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
            "what_you_have": what_you_have,
            "what_you_are_missing": what_you_are_missing,
            "is_eligible": is_eligible,
            "eligibility_reason": eligibility_reason,
            "strengths": strengths or ["Basic candidate foundational profile ready."],
            "weaknesses": weaknesses or ["No significant technical blockers identified."],
            "recommendations": recommendations or ["Review standard technical fundamentals and data structures."]
        }
