"""Module 1: Two-Pass Resume Taxonomy Extraction Engine.

Pass 1: Delegates to existing ResumeParser (no changes to original).
Pass 2: LLM-guided categorical bucketing with strict JSON Schema validation
        and deterministic cosine similarity matching against JD text.

This module is purely additive — it wraps, never replaces, the original parser.
"""

from __future__ import annotations

import re
import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.ai.factory import AIFactory
from app.schemas.taxonomy import (
    SkillTaxonomy,
    SkillTaxonomyResult,
    TaxonomyMatchResult,
)

logger = logging.getLogger("ai_interviewer.taxonomy_parser")

# ---------------------------------------------------------------------------
# Noise filter: these are NEVER core evaluation skills regardless of context.
# They belong in developer_tools or soft_skills_and_noise.
# ---------------------------------------------------------------------------
VANITY_NOISE_ITEMS: frozenset = frozenset({
    "github", "gitlab", "bitbucket", "sourcetree",
    "vs code", "vscode", "visual studio code", "pycharm", "intellij", "eclipse",
    "atom", "sublime text", "sublime",
    "slack", "teams", "microsoft teams", "zoom", "discord",
    "jira", "confluence", "trello", "notion", "asana", "monday.com",
    "postman", "insomnia", "swagger ui",
    "figma", "canva", "adobe xd",
    "agile", "scrum", "kanban", "safe", "waterfall",
    "communication", "teamwork", "leadership", "critical thinking",
    "problem solving", "time management", "adaptability",
    "ms office", "microsoft office", "word", "excel", "powerpoint",
    "google docs", "google sheets", "google slides",
    "windows", "macos", "chrome",
})

# Gemini JSON Schema for Pass-2 taxonomy extraction
TAXONOMY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "core_technical_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Programming languages (Python, Java, C++), core CS paradigms "
                "(Distributed Systems, RAG, WebSockets, Concurrency), ML/AI techniques "
                "(Transformers, Diffusion Models, RLHF, Vector Embeddings). "
                "NEVER include GitHub, VS Code, Agile, or collaboration tools here."
            )
        },
        "frameworks_and_libraries": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Application/ML frameworks: FastAPI, Django, Flask, React, Next.js, "
                "Vue, Angular, LangChain, HuggingFace, PyTorch, TensorFlow, Keras, "
                "Scikit-Learn, Pandas, NumPy, Spring Boot, Express."
            )
        },
        "developer_tools": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "DevOps, infrastructure, and build tools ONLY: Docker, Kubernetes, "
                "CI/CD, Terraform, Ansible, Jenkins, Git (the version-control protocol), "
                "AWS, Azure, GCP, Linux. "
                "EXCLUDE: GitHub (the website), VS Code, Slack, Jira, Postman."
            )
        },
        "domain_knowledge": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Applied technical domains: NLP, Computer Vision, MLOps, "
                "Quantitative Finance, Cybersecurity, Embedded Systems, "
                "Data Engineering, Bioinformatics, Robotics."
            )
        },
        "soft_skills_and_noise": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Non-technical items: Agile, Scrum, Communication, Leadership, "
                "GitHub (platform), VS Code, Postman, Jira, Slack, Trello."
            )
        }
    },
    "required": [
        "core_technical_skills",
        "frameworks_and_libraries",
        "developer_tools",
        "domain_knowledge",
        "soft_skills_and_noise"
    ]
}


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity (pure Python + built-in math — no ML model needed)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer returning lowercase tokens."""
    return re.findall(r"[a-z0-9#+.]+", text.lower())


def _build_tfidf_vector(
    doc_tokens: List[str],
    corpus_token_sets: List[List[str]]
) -> Dict[str, float]:
    """Build a TF-IDF weight dict for a single document given a corpus."""
    N = len(corpus_token_sets)
    tf: Dict[str, float] = {}
    for token in doc_tokens:
        tf[token] = tf.get(token, 0) + 1
    total = max(len(doc_tokens), 1)
    tf = {k: v / total for k, v in tf.items()}

    # IDF: log(N / df) with add-1 smoothing
    df: Dict[str, int] = {}
    for token_set in corpus_token_sets:
        unique_tokens = set(token_set)
        for t in unique_tokens:
            df[t] = df.get(t, 0) + 1

    vector: Dict[str, float] = {}
    for token, tf_val in tf.items():
        idf = math.log((N + 1) / (df.get(token, 0) + 1)) + 1.0
        vector[token] = tf_val * idf
    return vector


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse TF-IDF vectors."""
    dot = sum(vec_a.get(k, 0.0) * vec_b.get(k, 0.0) for k in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values())) or 1e-9
    norm_b = math.sqrt(sum(v * v for v in vec_b.values())) or 1e-9
    return dot / (norm_a * norm_b)


def compute_taxonomy_jd_similarity(
    taxonomy: SkillTaxonomy,
    jd_text: str
) -> TaxonomyMatchResult:
    """
    Compute match between candidate taxonomy and raw JD text.

    Uses:
    - 60%: TF-IDF cosine similarity between evaluation_skills text and JD text
    - 40%: Exact keyword overlap between evaluation_skills and JD skill tokens
    """
    evaluation_skills = (
        taxonomy.core_technical_skills
        + taxonomy.frameworks_and_libraries
        + taxonomy.domain_knowledge
    )
    if not evaluation_skills or not jd_text.strip():
        return TaxonomyMatchResult(match_percentage=0.0)

    candidate_text = " ".join(evaluation_skills).lower()
    jd_lower = jd_text.lower()

    # --- Cosine component ---
    cand_tokens = _tokenize(candidate_text)
    jd_tokens = _tokenize(jd_lower)
    corpus = [cand_tokens, jd_tokens]
    vec_c = _build_tfidf_vector(cand_tokens, corpus)
    vec_j = _build_tfidf_vector(jd_tokens, corpus)
    cosine_score = _cosine_similarity(vec_c, vec_j)

    # --- Keyword overlap component ---
    jd_skill_tokens = set(_tokenize(jd_lower))
    matching_strengths: List[str] = []
    partial_matches: List[str] = []

    for skill in evaluation_skills:
        skill_lower = skill.lower()
        skill_tokens = set(_tokenize(skill_lower))
        if not skill_tokens:
            continue

        if skill_tokens.issubset(jd_skill_tokens):
            matching_strengths.append(skill)
        elif skill_tokens & jd_skill_tokens:
            partial_matches.append(skill)

    overlap_ratio = (
        len(matching_strengths) + 0.5 * len(partial_matches)
    ) / max(len(evaluation_skills), 1)

    final_pct = round(
        min(100.0, (cosine_score * 60.0) + (overlap_ratio * 40.0)), 1
    )

    return TaxonomyMatchResult(
        match_percentage=final_pct,
        matching_strengths=matching_strengths,
        partial_matches=partial_matches,
    )


# ---------------------------------------------------------------------------
# Main TaxonomyParser class
# ---------------------------------------------------------------------------

class TaxonomyParser:
    """
    Two-pass taxonomy enrichment engine.

    Usage:
        result: SkillTaxonomyResult = await TaxonomyParser.enrich_profile(raw_parsed_dict)
    """

    @staticmethod
    def _apply_noise_filter(taxonomy_dict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Post-process LLM output to catch any vanity items that slipped through
        into core/framework buckets, and move them to soft_skills_and_noise.
        """
        clean = {k: list(v) for k, v in taxonomy_dict.items()}
        noise_bucket = clean.setdefault("soft_skills_and_noise", [])

        for bucket in ("core_technical_skills", "frameworks_and_libraries", "developer_tools"):
            survivors: List[str] = []
            for skill in clean.get(bucket, []):
                if skill.lower().strip() in VANITY_NOISE_ITEMS:
                    if skill not in noise_bucket:
                        noise_bucket.append(skill)
                else:
                    survivors.append(skill)
            clean[bucket] = survivors

        return clean

    @staticmethod
    async def enrich_profile(
        parsed_profile: Dict[str, Any],
        raw_text_snippet: Optional[str] = None
    ) -> SkillTaxonomyResult:
        """
        Pass 2: Take the raw parsed profile dict (from ResumeParser) and
        run LLM-guided categorical bucketing with noise filtering.

        Falls back to heuristic rule-based bucketing if LLM call fails.
        """
        raw_skills: List[str] = parsed_profile.get("skills", []) or []
        technologies: List[str] = parsed_profile.get("technologies", []) or []
        all_input_skills = list(dict.fromkeys(raw_skills + technologies))  # deduplicate, preserve order

        if not all_input_skills:
            empty_taxonomy = SkillTaxonomy()
            return SkillTaxonomyResult(
                taxonomy=empty_taxonomy,
                raw_skills=all_input_skills,
                evaluation_skills=[],
                noise_filtered=[],
            )

        # Build context from projects too
        project_techs: List[str] = []
        for proj in parsed_profile.get("projects", []):
            project_techs.extend(proj.get("technologies", []) if isinstance(proj, dict) else [])
        context_skills = list(dict.fromkeys(all_input_skills + project_techs))

        prompt = f"""You are an expert technical recruiter performing precise skill taxonomy classification.

Given the following extracted skills from a resume, classify EACH skill into EXACTLY ONE of the five categories.
No skill should appear in more than one category.

CRITICAL RULES:
1. "GitHub" → soft_skills_and_noise (it's a platform, not a skill; "Git" → developer_tools)
2. "VS Code", "PyCharm", "IntelliJ" → soft_skills_and_noise (IDE ≠ technical skill)
3. "Agile", "Scrum", "Kanban" → soft_skills_and_noise
4. "Slack", "Jira", "Confluence", "Trello", "Notion" → soft_skills_and_noise
5. "Postman" → soft_skills_and_noise (API testing tool, not a technical competency)
6. Programming languages (Python, Java, Go, Rust) → core_technical_skills
7. ML techniques (RAG, RLHF, Transformers, Vector Embeddings) → core_technical_skills
8. Frameworks (FastAPI, React, PyTorch, LangChain) → frameworks_and_libraries
9. Cloud platforms (AWS, GCP, Azure) → developer_tools
10. Domains (NLP, Computer Vision, MLOps) → domain_knowledge

Skills to classify:
{context_skills}

Return ONLY valid JSON matching the exact schema — no markdown, no explanation:
{{
  "core_technical_skills": [],
  "frameworks_and_libraries": [],
  "developer_tools": [],
  "domain_knowledge": [],
  "soft_skills_and_noise": []
}}"""

        taxonomy_dict: Optional[Dict[str, Any]] = None
        try:
            llm = AIFactory.get_llm_provider()
            taxonomy_dict = await llm.generate_json(
                prompt=prompt,
                system_prompt=(
                    "You are a precise skill taxonomy classifier. "
                    "Output only valid JSON. Never invent skills not present in the input list."
                ),
                schema=TAXONOMY_JSON_SCHEMA,
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception as exc:
            logger.warning(f"TaxonomyParser LLM pass failed: {exc}. Falling back to heuristic.")
            taxonomy_dict = None

        if taxonomy_dict and isinstance(taxonomy_dict, dict):
            cleaned = TaxonomyParser._apply_noise_filter(taxonomy_dict)
        else:
            # Heuristic fallback: bucket by canonical prefixes
            cleaned = TaxonomyParser._heuristic_bucket(context_skills)

        try:
            taxonomy = SkillTaxonomy(**{
                k: [s for s in v if isinstance(s, str)]
                for k, v in cleaned.items()
            })
        except Exception as ve:
            logger.error(f"SkillTaxonomy validation error: {ve}")
            taxonomy = SkillTaxonomy()

        evaluation_skills = list(dict.fromkeys(
            taxonomy.core_technical_skills
            + taxonomy.frameworks_and_libraries
            + taxonomy.domain_knowledge
        ))
        noise_filtered = list(dict.fromkeys(taxonomy.soft_skills_and_noise))

        return SkillTaxonomyResult(
            taxonomy=taxonomy,
            raw_skills=all_input_skills,
            evaluation_skills=evaluation_skills,
            noise_filtered=noise_filtered,
            taxonomy_generated_at=datetime.utcnow(),
        )

    @staticmethod
    def _heuristic_bucket(skills: List[str]) -> Dict[str, List[str]]:
        """
        Rule-based fallback taxonomy bucketing using keyword heuristics.
        Used when the LLM call fails.
        """
        core = []
        frameworks = []
        tools = []
        domain = []
        noise = []

        _LANG_KEYWORDS = {
            "python", "java", "c++", "c#", "go", "golang", "rust", "typescript",
            "javascript", "kotlin", "swift", "scala", "r", "php", "dart", "c",
            "sql", "nosql", "graphql", "grpc", "websockets", "webrtc",
            "distributed systems", "microservices", "algorithms",
            "data structures", "system design", "oop", "concurrency",
            "rag", "llm", "transformers", "vector embeddings", "rlhf",
            "machine learning", "deep learning", "neural networks",
        }
        _FRAMEWORK_KEYWORDS = {
            "fastapi", "django", "flask", "react", "next.js", "vue", "angular",
            "node.js", "express", "spring boot", "asp.net", "pytorch", "tensorflow",
            "keras", "scikit-learn", "pandas", "numpy", "opencv", "langchain",
            "huggingface", "streamlit", "celery", "sqlalchemy", "prisma",
            "tailwind", "bootstrap", "redux", "graphene",
        }
        _TOOL_KEYWORDS = {
            "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "google cloud",
            "ci/cd", "terraform", "ansible", "jenkins", "nginx", "linux",
            "git", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        }
        _DOMAIN_KEYWORDS = {
            "nlp", "computer vision", "mlops", "data engineering", "cybersecurity",
            "quantitative finance", "embedded systems", "robotics", "bioinformatics",
            "cloud architecture", "devops",
        }

        for skill in skills:
            lower = skill.lower().strip()
            if lower in VANITY_NOISE_ITEMS:
                noise.append(skill)
            elif lower in _LANG_KEYWORDS:
                core.append(skill)
            elif lower in _FRAMEWORK_KEYWORDS:
                frameworks.append(skill)
            elif lower in _TOOL_KEYWORDS:
                tools.append(skill)
            elif lower in _DOMAIN_KEYWORDS:
                domain.append(skill)
            else:
                # Default: put in core if it looks like a technology
                if re.search(r"[A-Z]", skill) and len(skill) <= 30:
                    core.append(skill)
                else:
                    noise.append(skill)

        return {
            "core_technical_skills": core,
            "frameworks_and_libraries": frameworks,
            "developer_tools": tools,
            "domain_knowledge": domain,
            "soft_skills_and_noise": noise,
        }
