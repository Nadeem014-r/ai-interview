"""Interview Persona & Tailored Framing Builder.

Constructs company-, role-, and culture-grounded AI interviewer personas
for realistic viva and placement practice across Text, Voice, and Video modes.
"""

from typing import Dict, Any, Optional, List
from app.db.models import Company, Role
from app.ai.factory import AIFactory


class InterviewPersonaBuilder:
    """Builds authoritative, company-grounded interviewer personas and warm-up prompts."""

    @staticmethod
    def get_persona_summary(company: Optional[Company], role: Optional[Role], target_level: str = "entry") -> Dict[str, Any]:
        company_name = company.name if company else "Tech Company"
        role_title = role.title if role else "Software Engineer"
        culture_keywords = company.culture_keywords if (company and company.culture_keywords) else ["Technical Excellence", "Collaboration", "Problem Solving"]
        role_level = role.level if (role and role.level) else target_level.capitalize()

        from app.companies.strategy_engine import CompanyStrategyEngine
        profile = CompanyStrategyEngine.get_company_profile(company.slug if company else None)
        
        interviewer_title = f"Senior Hiring Manager & Technical Lead at {company_name}"
        framing = (
            f"You are conducting a professional hiring interview as a {interviewer_title} "
            f"for the '{role_title}' ({role_level}) position. "
            f"Ground your tone and expectations in {company_name}'s engineering standards, interview style ({profile.question_style}), "
            f"and culture keywords: {', '.join(culture_keywords)}."
        )

        return {
            "company_name": company_name,
            "role_title": role_title,
            "role_level": role_level,
            "culture_keywords": culture_keywords,
            "interviewer_title": interviewer_title,
            "persona_framing": framing,
            "question_style": profile.question_style,
            "difficulty_profile": profile.difficulty_profile,
            "public_pattern_notes": profile.public_pattern_notes
        }

    @staticmethod
    async def generate_warmup_question(
        company: Optional[Company],
        role: Optional[Role],
        candidate_name: Optional[str] = None,
        question_index: int = 0,
        resume_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates genuine warm-up/personal questions tailored to the company and role.
        Stage 1 MUST ask personal/warm-up questions before academic/technical questions.
        """
        company_name = company.name if company else "our team"
        role_title = role.title if role else "Software Engineer"
        culture_kw = ", ".join(company.culture_keywords[:3]) if (company and company.culture_keywords) else "engineering excellence"
        cand_greeting = f"Hello {candidate_name.split()[0]}, " if candidate_name else "Hello, "

        # LLM tailored dynamic warm-up generation with grounded fallback
        llm = AIFactory.get_llm_provider()
        prompt = f"""
Generate a warm, professional, non-technical Stage 1 warm-up interview question (question #{question_index + 1} of interview).
Interviewer: Senior Technical Hiring Manager at {company_name}
Target Role: {role_title}
Company Culture Focus: {culture_kw}
Candidate Background Context: {resume_context or "Recent graduate / candidate"}

RULES FOR WARM-UP QUESTIONS:
- Do NOT ask technical algorithms, syntax, or textbook definitions.
- Focus strictly on personal journey, background introduction, motivation for {company_name}, or general collaboration style.
- Include natural conversational framing from {company_name}.

Return JSON:
{{
    "question_text": "The personal warm-up question text",
    "expected_concepts": ["Clear communication", "Self-introduction", "Company alignment"],
    "follow_ups": ["What specific aspect of our engineering culture resonates with you most?"]
}}
"""
        try:
            res = await llm.generate_json(
                prompt,
                system_prompt=f"You are a friendly yet discerning senior hiring manager at {company_name} opening an interview."
            )
            if res and isinstance(res, dict) and res.get("question_text"):
                return {
                    "question_text": res["question_text"],
                    "expected_concepts": res.get("expected_concepts", ["Clear communication", "Self-introduction", "Company alignment"]),
                    "follow_ups": res.get("follow_ups", ["Can you elaborate on your motivation for this role?"]),
                    "topic": "Introduction & Motivation",
                    "question_type": "hr",
                    "difficulty": "easy"
                }
        except Exception:
            pass

        # Deterministic company-tailored warm-up fallbacks
        if question_index == 0:
            q_text = (
                f"{cand_greeting}welcome to your interview for the {role_title} role at {company_name}! "
                f"To start off, could you tell me a little bit about yourself, your educational background, "
                f"and what specifically drew you to apply to {company_name}?"
            )
            concepts = ["Personal introduction", "Educational background", f"Interest in {company_name}"]
        elif question_index == 1:
            q_text = (
                f"Thank you for sharing that. Looking at your journey, what has been your most rewarding project or experience so far, "
                f"and how does it prepare you for the day-to-day challenges of a {role_title} at {company_name}?"
            )
            concepts = ["Project walkthrough", "Personal impact", "Role relevance"]
        else:
            q_text = (
                f"At {company_name}, we place high value on {culture_kw}. Could you share an example of a time you had to "
                f"collaborate with others under a tight deadline or navigate an unexpected project hurdle?"
            )
            concepts = ["Teamwork", "Adaptability", f"Alignment with {culture_kw}"]

        return {
            "question_text": q_text,
            "expected_concepts": concepts,
            "follow_ups": [f"What aspect of {company_name}'s tech stack or mission excites you most?"],
            "topic": "Introduction & Motivation",
            "question_type": "hr",
            "difficulty": "easy"
        }
