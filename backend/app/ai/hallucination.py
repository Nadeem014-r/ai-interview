"""Phase 8: Hallucination Prevention & Evidence Verification Controls.

Provides strict grounding rules and fact-verification helpers to prevent
the LLM from inventing unverified company facts, fake candidate history, or false claims.
"""

from typing import Dict, Any, List, Optional


GROUNDING_INSTRUCTION = """
STRICT GROUNDING REQUIREMENT:
- All statements must be directly supported by verified facts in the provided evidence.
- Do NOT invent company background, job requirements, or candidate experiences.
- If information is missing or unclear, respond with 'Information not provided in context' or null.
- Distinguish verified explicit facts from model-inferred deductions.
"""

def add_grounding_system_instruction(base_system_prompt: Optional[str] = None) -> str:
    """Enhance a system prompt with strict anti-hallucination rules."""
    prefix = f"{base_system_prompt.strip()}\n\n" if base_system_prompt else ""
    return f"{prefix}{GROUNDING_INSTRUCTION.strip()}"


def build_research_synthesis_prompt(
    company_name: str,
    role_title: str,
    evidence_chunks: List[str]
) -> str:
    """
    Construct a research synthesis prompt that forbids hallucination if evidence is absent.
    """
    if not evidence_chunks:
        evidence_text = "NO VERIFIED SOURCES AVAILABLE."
    else:
        evidence_text = "\n---\n".join(evidence_chunks)

    return f"""
Synthesize verified interview intelligence for {company_name} - {role_title}.

VERIFIED EVIDENCE:
{evidence_text}

INSTRUCTIONS:
1. Extract culture keywords, key topics, required skills, and interview categories ONLY if present in the evidence.
2. If evidence is empty or missing specific details, return empty lists [] or indicate 'Not provided'.
3. Do NOT make assumptions or invent details about {company_name}.

Return JSON:
{{
    "description": "verified summary or null",
    "required_skills": ["verified skill"],
    "key_topics": ["verified topic"],
    "interview_categories": ["verified category"],
    "culture_keywords": ["verified keyword"],
    "confidence_level": "high | medium | low | none"
}}
"""
