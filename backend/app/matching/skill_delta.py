"""Module 2B: Skill Gap Delta Engine.

Computes:
  1. match_percentage — weighted cosine + keyword overlap (60/40)
  2. matching_strengths — confirmed present in both
  3. critical_gaps — required JD skills absent from core/framework buckets
  4. emerging_skill_gaps — skills added to JD since last cached snapshot
  5. nice_to_have_gaps — preferred JD skills the candidate lacks
  6. noise_discarded — JD mentions matched only in noise buckets (excluded from gaps)
"""

from __future__ import annotations

import re
import math
import logging
from typing import List, Dict, Set, Optional, Tuple, Any
from datetime import datetime, timezone

from app.schemas.taxonomy import SkillTaxonomy, SkillDeltaResult, ScrapingResult
from app.resume.taxonomy_parser import _tokenize, _build_tfidf_vector, _cosine_similarity

logger = logging.getLogger("ai_interviewer.skill_delta")

# Weights for the composite match score
_COSINE_WEIGHT = 0.60
_OVERLAP_WEIGHT = 0.40


def _normalize_skill(skill: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation for comparison."""
    return re.sub(r"[^a-z0-9#+. ]", "", skill.lower().strip())


def _skills_to_token_set(skills: List[str]) -> Set[str]:
    """Convert a list of skills into a flat set of single tokens for overlap."""
    tokens: Set[str] = set()
    for skill in skills:
        tokens.update(_tokenize(skill))
    return tokens


def _fuzzy_match(skill_a: str, skill_b: str) -> bool:
    """
    True if the two skill strings are semantically equivalent:
    - exact normalized match
    - one is a token subset of the other (min 4-char tokens)
    """
    a_norm = _normalize_skill(skill_a)
    b_norm = _normalize_skill(skill_b)
    if a_norm == b_norm:
        return True
    a_toks = {t for t in _tokenize(a_norm) if len(t) >= 4}
    b_toks = {t for t in _tokenize(b_norm) if len(t) >= 4}
    if not a_toks or not b_toks:
        return False
    return a_toks.issubset(b_toks) or b_toks.issubset(a_toks)


def _find_match(skill: str, candidate_set: List[str]) -> Optional[str]:
    """Return the matched candidate skill string, or None."""
    for c in candidate_set:
        if _fuzzy_match(skill, c):
            return c
    return None


class SkillGapDeltaEngine:
    """
    Computes a comprehensive skill delta between a candidate's parsed taxonomy
    and the live JD skill requirements from the scraping service.
    """

    @staticmethod
    def compute_match(
        candidate_taxonomy: SkillTaxonomy,
        jd_result: ScrapingResult,
        previous_required_skills: Optional[List[str]] = None,
        job_id: Optional[int] = None,
    ) -> SkillDeltaResult:
        """
        Main entry point.

        Args:
            candidate_taxonomy: SkillTaxonomy from TaxonomyParser.enrich_profile()
            jd_result: ScrapingResult from JDScrapingService.scrape()
            previous_required_skills: skills from last cached JD snapshot (for delta detection)
            job_id: optional DB job ID for the result object
        """
        # --- Candidate evaluation skills (buckets that count) ---
        candidate_eval: List[str] = (
            candidate_taxonomy.core_technical_skills
            + candidate_taxonomy.frameworks_and_libraries
            + candidate_taxonomy.domain_knowledge
        )
        # Candidate noise (tools + soft skills) — used to identify noise discards
        candidate_noise: List[str] = (
            candidate_taxonomy.developer_tools
            + candidate_taxonomy.soft_skills_and_noise
        )

        required = jd_result.required_skills or []
        nice_to_have = jd_result.nice_to_have_skills or []

        # --- Cosine similarity component ---
        cosine_pct = SkillGapDeltaEngine._compute_cosine_pct(candidate_eval, required)

        # --- Keyword overlap analysis ---
        matching_strengths: List[str] = []
        critical_gaps: List[str] = []
        noise_discarded: List[str] = []
        nice_to_have_gaps: List[str] = []

        for jd_skill in required:
            matched_eval = _find_match(jd_skill, candidate_eval)
            if matched_eval:
                if jd_skill not in matching_strengths:
                    matching_strengths.append(jd_skill)
            else:
                # Check if it matches only in noise buckets
                matched_noise = _find_match(jd_skill, candidate_noise)
                if matched_noise:
                    if jd_skill not in noise_discarded:
                        noise_discarded.append(jd_skill)
                else:
                    if jd_skill not in critical_gaps:
                        critical_gaps.append(jd_skill)

        for jd_skill in nice_to_have:
            matched_eval = _find_match(jd_skill, candidate_eval)
            if not matched_eval and jd_skill not in nice_to_have_gaps:
                nice_to_have_gaps.append(jd_skill)

        # --- Overlap ratio ---
        overlap_ratio = (
            len(matching_strengths) / max(len(required), 1)
        )

        # --- Composite match percentage ---
        match_pct = round(
            min(100.0, (cosine_pct * _COSINE_WEIGHT * 100.0) + (overlap_ratio * _OVERLAP_WEIGHT * 100.0)),
            1,
        )

        # --- Emerging skill gap detection ---
        emerging_skill_gaps = SkillGapDeltaEngine._detect_emerging_gaps(
            current_required=required,
            previous_required=previous_required_skills or [],
            candidate_eval=candidate_eval,
        )

        return SkillDeltaResult(
            job_id=job_id,
            company_name=jd_result.company_name,
            role_title=jd_result.role_title,
            match_percentage=match_pct,
            matching_strengths=matching_strengths,
            critical_gaps=critical_gaps,
            emerging_skill_gaps=emerging_skill_gaps,
            nice_to_have_gaps=nice_to_have_gaps,
            noise_discarded=noise_discarded,
            jd_scraped_at=jd_result.scraped_at,
            computed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _compute_cosine_pct(candidate_eval: List[str], jd_required: List[str]) -> float:
        """
        Compute cosine similarity between candidate eval skills and JD required skills.
        Returns value in [0, 1].
        """
        if not candidate_eval or not jd_required:
            return 0.0
        cand_text = " ".join(candidate_eval)
        jd_text = " ".join(jd_required)
        cand_tokens = _tokenize(cand_text)
        jd_tokens = _tokenize(jd_text)
        if not cand_tokens or not jd_tokens:
            return 0.0
        corpus = [cand_tokens, jd_tokens]
        vec_c = _build_tfidf_vector(cand_tokens, corpus)
        vec_j = _build_tfidf_vector(jd_tokens, corpus)
        return _cosine_similarity(vec_c, vec_j)

    @staticmethod
    def _detect_emerging_gaps(
        current_required: List[str],
        previous_required: List[str],
        candidate_eval: List[str],
    ) -> List[str]:
        """
        Identify skills newly added to JD since the last cached snapshot
        that the candidate is also missing.

        Returns a list of human-readable strings describing the emerging gaps.
        """
        if not previous_required:
            return []

        prev_normalized = {_normalize_skill(s) for s in previous_required}
        emerging: List[str] = []
        for skill in current_required:
            norm = _normalize_skill(skill)
            is_new = norm not in prev_normalized
            is_missing = not _find_match(skill, candidate_eval)
            if is_new and is_missing:
                emerging.append(skill)

        return emerging

    @staticmethod
    def format_gap_narrative(result: SkillDeltaResult) -> str:
        """
        Generate a concise, natural-language gap narrative for interview coaching.
        """
        lines: List[str] = []

        lines.append(
            f"**Match Score: {result.match_percentage:.0f}%** "
            f"for {result.role_title} at {result.company_name}."
        )

        if result.matching_strengths:
            strengths_str = ", ".join(result.matching_strengths[:8])
            lines.append(f"✅ **Confirmed Strengths**: {strengths_str}.")

        if result.critical_gaps:
            gaps_str = ", ".join(result.critical_gaps[:8])
            lines.append(f"⚠️ **Critical Gaps**: {gaps_str}.")

        if result.emerging_skill_gaps:
            emerging_str = ", ".join(result.emerging_skill_gaps[:5])
            lines.append(
                f"🔥 **Emerging Requirements** (recently added to this role): "
                f"{emerging_str} — these are absent from your resume and gaining traction."
            )

        if result.nice_to_have_gaps:
            nice_str = ", ".join(result.nice_to_have_gaps[:5])
            lines.append(f"💡 **Nice-to-Have Gaps**: {nice_str}.")

        if result.noise_discarded:
            noise_str = ", ".join(result.noise_discarded[:3])
            lines.append(
                f"ℹ️ Tool mentions ({noise_str}) were excluded from gap scoring "
                f"as they are platform/workflow tools, not core competencies."
            )

        return "\n".join(lines)
