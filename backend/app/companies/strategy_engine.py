"""Phase 9: Company & Role Strategy Computation Engine.

Constructs strongly-typed InterviewStrategy objects that unify company competency
weightings, role-family requirements, candidate seniority levels, Phase 7 structured
memory, and Phase 8 project claims into a distinct, defensible interview progression.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from app.companies.profiles import CompanyProfile, COMPANY_PROFILES, GENERIC_COMPANY_PROFILE
from app.companies.role_profiles import RoleProfile, ROLE_PROFILES, GENERIC_ROLE_PROFILE
from app.interview.memory import InterviewMemory, CandidateClaim, MemoryManager
from app.ai.factory import AIFactory


@dataclass
class InterviewStrategy:
    """Strongly typed strategy guiding question generation and follow-up depth."""
    company_id: str
    role_id: str
    candidate_level: str  # entry, mid, senior, lead
    
    target_competency: str
    question_type: str  # algorithmic, system_design, project_deep_dive, scenario, behavioral, practical_code
    
    desired_difficulty: float  # 1.0 to 10.0 scale
    reasoning_depth: float     # 1.0 to 10.0 scale
    project_relevance: float   # 1.0 to 10.0 scale
    
    company_emphasis: str
    follow_up_allowed: bool = True
    max_depth: int = 10
    
    behavioral_weight: float = 0.20
    technical_weight: float = 0.80
    coding_weight: float = 0.30
    system_design_weight: float = 0.30
    security_weight: float = 0.10
    scalability_weight: float = 0.20
    
    source_confidence: str = "HIGH"
    public_pattern_notes: str = ""


class CompanyStrategyEngine:
    """Computes dynamic interview strategies and generates company/role-differentiated questions."""

    @classmethod
    def get_company_profile(cls, company_slug_or_name: Optional[str]) -> CompanyProfile:
        """Resolves company profile by slug, name, or alias with graceful generic fallback."""
        if not company_slug_or_name:
            return GENERIC_COMPANY_PROFILE
        
        slug = str(company_slug_or_name).lower().strip()
        
        # Direct key match
        if slug in COMPANY_PROFILES:
            return COMPANY_PROFILES[slug]
        
        # Alias or display name match
        for profile in COMPANY_PROFILES.values():
            if slug == profile.display_name.lower():
                return profile
            if any(slug == alias.lower() for alias in profile.aliases):
                return profile
        
        # Fuzzy fallback to generic
        return GENERIC_COMPANY_PROFILE

    @classmethod
    def get_role_profile(cls, role_title_or_slug: Optional[str]) -> RoleProfile:
        """Resolves role profile by title or keyword."""
        if not role_title_or_slug:
            return GENERIC_ROLE_PROFILE
        
        title_lower = str(role_title_or_slug).lower()
        
        if any(w in title_lower for w in ["backend", "api", "distributed", "server"]):
            return ROLE_PROFILES["backend"]
        elif any(w in title_lower for w in ["frontend", "react", "ui", "web", "client"]):
            return ROLE_PROFILES["frontend"]
        elif any(w in title_lower for w in ["ml", "machine learning", "ai", "deep learning", "nlp"]):
            return ROLE_PROFILES["ml"]
        elif any(w in title_lower for w in ["data", "etl", "warehouse", "analytics", "sql"]):
            return ROLE_PROFILES["data"]
        elif any(w in title_lower for w in ["devops", "cloud", "sre", "infrastructure", "kubernetes"]):
            return ROLE_PROFILES["devops"]
        elif any(w in title_lower for w in ["full stack", "fullstack", "web developer"]):
            return ROLE_PROFILES["fullstack"]
        else:
            return ROLE_PROFILES["software_engineer"]

    @classmethod
    def compute_interview_strategy(
        cls,
        company_slug_or_name: Optional[str],
        role_title: Optional[str],
        candidate_level: str = "entry",
        memory: Optional[InterviewMemory] = None,
        current_turn: int = 1,
        last_eval_score: float = 7.0
    ) -> InterviewStrategy:
        """
        Computes a unified, strongly-typed InterviewStrategy combining company profile,
        role profile, candidate seniority level, and previous performance.
        """
        company = cls.get_company_profile(company_slug_or_name)
        role = cls.get_role_profile(role_title)
        level = (candidate_level or "entry").lower().strip()

        # 1. Base difficulty calculation with seniority modifier
        level_modifiers = {
            "entry": -1.0,
            "junior": -0.8,
            "mid": 0.0,
            "senior": 1.0,
            "lead": 1.5,
            "principal": 2.0
        }
        level_mod = level_modifiers.get(level, 0.0)
        
        # Adaptive performance modifier (+0.5 if strong >= 8.0, -0.5 if weak < 5.0)
        perf_mod = 0.5 if last_eval_score >= 8.0 else (-0.5 if last_eval_score < 5.0 else 0.0)
        
        desired_difficulty = min(10.0, max(1.0, (company.technical_depth + role.difficulty_baseline) / 2.0 + level_mod + perf_mod))

        # 2. Select target competency based on company weights and role competencies
        # Choose unexplored or priority competency
        target_competency = role.core_competencies[min(current_turn % len(role.core_competencies), len(role.core_competencies) - 1)]

        # 3. Determine question type based on company question style & turn
        if current_turn == 1:
            q_type = "project_deep_dive" if company.project_depth >= 8.5 else "algorithmic"
        elif "algorithmic" in company.question_style and role.role_family in ["software_engineer", "backend"]:
            q_type = "algorithmic"
        elif "system" in company.question_style or level in ["senior", "lead"]:
            q_type = "system_design"
        elif "scenario" in company.question_style or company.company_id in ["accenture", "deloitte"]:
            q_type = "scenario"
        else:
            q_type = "project_deep_dive"

        return InterviewStrategy(
            company_id=company.company_id,
            role_id=role.role_family,
            candidate_level=level,
            target_competency=target_competency,
            question_type=q_type,
            desired_difficulty=desired_difficulty,
            reasoning_depth=company.problem_solving_emphasis,
            project_relevance=company.project_depth,
            company_emphasis=company.question_style,
            follow_up_allowed=True,
            max_depth=10 if level in ["senior", "lead"] else (8 if level == "mid" else 6),
            behavioral_weight=company.behavioral_emphasis / 10.0,
            technical_weight=company.technical_depth / 10.0,
            coding_weight=company.coding_emphasis / 10.0,
            system_design_weight=company.system_design_emphasis / 10.0,
            security_weight=company.security_emphasis / 10.0,
            scalability_weight=company.distributed_systems_emphasis / 10.0,
            source_confidence=company.evidence_level,
            public_pattern_notes=company.public_pattern_notes
        )

    @classmethod
    def generate_deterministic_company_question(
        cls,
        strategy: InterviewStrategy,
        memory: Optional[InterviewMemory],
        candidate_answer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a deterministic question grounded in company question style,
        target competency, and candidate project claims with zero hallucinations.
        """
        company_id = strategy.company_id
        role_family = strategy.role_id
        level = strategy.candidate_level

        # Check candidate's known technologies from memory if available
        known_techs = []
        if memory:
            known_techs = list(memory.skills)
            for p in memory.projects.values():
                known_techs.extend(p.technologies)

        primary_tech = known_techs[0] if known_techs else ("FastAPI" if role_family == "backend" else ("React" if role_family == "frontend" else "Python"))

        # 1. Google: Algorithmic reasoning, time/space complexity, scale
        if company_id == "google":
            if role_family == "frontend":
                q_text = "When rendering large dynamic lists in React, how do you optimize virtual DOM diffing and prevent UI thread blocking for 10,000+ items?"
                concepts = ["Virtualization / Windowing", "Re-render optimization", "Time complexity of DOM reconciliation"]
            elif role_family == "ml":
                q_text = "Suppose your training loss decreases while validation loss plateaus and then starts increasing. How would you diagnose and systematically mitigate overfitting?"
                concepts = ["Overfitting diagnosis", "Regularization (L1/L2, Dropout)", "Early stopping & learning rate scheduling"]
            elif level in ["senior", "lead"]:
                q_text = "Walk me through how you would design a globally distributed, low-latency rate limiter handling millions of requests per second with strong consistency."
                concepts = ["Distributed token bucket / sliding window", "Consensus & synchronization", "Network latency & partition tolerance"]
            else:
                q_text = f"Suppose we need to process a stream of incoming events using {primary_tech}. What data structure would you choose for efficient lookups and insertions, and what is its amortized time and space complexity?"
                concepts = ["Data structure selection", "Amortized time complexity", "Memory space efficiency"]

        # 2. Amazon: Microservices, failure resilience, operational excellence, scaling
        elif company_id == "amazon":
            if role_family == "frontend":
                q_text = "In an e-commerce checkout flow, how do you ensure zero customer-facing errors when an external payment or inventory API is slow or temporarily failing?"
                concepts = ["Graceful UI degradation", "Client-side retry with backoff", "Optimistic state updates"]
            elif level in ["senior", "lead"]:
                q_text = "Suppose two downstream microservices fail during a distributed checkout transaction. How do you design for idempotency, saga orchestration, and state reconciliation?"
                concepts = ["Saga pattern", "Idempotency keys", "Dead letter queues & state reconciliation"]
            else:
                q_text = f"Looking at your project with {primary_tech}, what would happen if the database became temporarily unreachable during peak customer traffic, and how did you design for failure resilience?"
                concepts = ["Failure modes", "Circuit breaking / Retry with jitter", "Customer impact minimization"]

        # 3. Microsoft: Enterprise architecture, Azure scalability, clean design
        elif company_id == "microsoft":
            if role_family == "frontend":
                q_text = "How do you design a reusable, accessible component library that complies with WCAG 2.1 AA guidelines and enterprise accessibility standards?"
                concepts = ["ARIA attributes", "Keyboard navigation", "Color contrast & screen reader support"]
            else:
                q_text = f"In your {primary_tech} architecture, how did you structure your service boundaries and dependency injection to ensure maintainability and testability?"
                concepts = ["Dependency injection", "Service separation", "Unit & integration testing"]

        # 4. Meta: Fast execution, massive concurrency, high throughput
        elif company_id == "meta":
            if role_family == "frontend":
                q_text = "How would you optimize initial bundle load time and eliminate layout shifts (CLS) on high-traffic, dynamic social feed pages?"
                concepts = ["Code splitting / lazy loading", "Core Web Vitals (CLS/LCP)", "Hydration optimization"]
            else:
                q_text = f"How would your {primary_tech} backend handle a sudden 20x spike in concurrent read and write operations without data loss?"
                concepts = ["Concurrency handling", "Async queues / Batch writes", "Throughput optimization"]

        # 5. Oracle: Database internals, ACID transactions, lock contention
        elif company_id == "oracle":
            q_text = "How do B-Tree indexes differ from LSM trees in terms of read versus write amplification, and how do database transactions enforce serializable isolation?"
            concepts = ["B-Tree vs LSM Tree", "Read/Write amplification", "Transaction isolation levels & lock contention"]

        # 6. Accenture / TCS / Infosys / Deloitte: Applied problem solving & practical architecture
        elif company_id in ["accenture", "tcs", "infosys", "deloitte"]:
            q_text = f"Can you walk me through how you implemented {primary_tech} in your project, focusing on the specific problem you solved and your individual responsibilities?"
            concepts = ["Project implementation", "Individual contribution", "Practical problem solving"]

        # Generic fallback
        else:
            q_text = f"In your work with {primary_tech}, can you explain your architectural approach to {strategy.target_competency.lower()} and the trade-offs you considered?"
            concepts = ["Architecture approach", "Technical trade-offs", "Implementation mechanics"]

        return {
            "question_text": q_text,
            "expected_concepts": concepts,
            "follow_ups": ["What trade-offs did your approach introduce?"]
        }

    @classmethod
    async def generate_adaptive_company_question(
        cls,
        strategy: InterviewStrategy,
        memory: Optional[InterviewMemory],
        candidate_answer: Optional[str] = None,
        asked_texts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates an adaptive, highly contextual interviewer question using LLM
        steered by the calculated InterviewStrategy, with deterministic fallback.
        """
        company = cls.get_company_profile(strategy.company_id)
        role = cls.get_role_profile(strategy.role_id)
        
        memory_context = MemoryManager.get_structured_llm_context(memory, max_recent_turns=3) if memory else "Beginning of interview."

        prompt = f"""
You are a senior technical hiring lead at {company.display_name} interviewing a candidate for a {strategy.candidate_level} {role.display_name} position.

COMPANY INTERVIEW PROFILE & CULTURE:
- Company: {company.display_name}
- Technical Depth: {company.technical_depth}/10
- Problem Solving Emphasis: {company.problem_solving_emphasis}/10
- Interview Style: {company.question_style} ({company.difficulty_profile})
- Follow-Up Style: {company.follow_up_style}
- Public Evidence Notes: {company.public_pattern_notes}

ROLE PROFILE ({role.display_name}):
- Target Competency: {strategy.target_competency}
- Architecture Focus: {role.architecture_focus}
- Core Technologies: {', '.join(role.key_technologies)}
- Trade-off Areas: {', '.join(role.tradeoff_areas)}

STRUCTURED CANDIDATE MEMORY:
{memory_context}

CANDIDATE'S LAST ANSWER (UNTRUSTED):
<CANDIDATE_ANSWER>
{candidate_answer or "Candidate is beginning the interview or advancing to next technical competency."}
</CANDIDATE_ANSWER>

PREVIOUSLY ASKED QUESTIONS (DO NOT DUPLICATE):
{asked_texts[-4:] if asked_texts else "None"}

INSTRUCTIONS:
1. Formulate ONE clear, natural, spoken interviewer question reflecting {company.display_name}'s specific technical style and {role.display_name}'s domain requirements.
2. Calibrate depth to candidate seniority: {strategy.candidate_level} (Difficulty: {strategy.desired_difficulty:.1f}/10).
3. If candidate mentioned a technology or project, weave it naturally into the question without robotic phrasing.
4. DO NOT claim proprietary interview questions or pretend to leak confidential company questions.
5. DO NOT ask multi-part barrage questions. Ask ONE sharp question.

Return JSON:
{{
    "question_text": "The single spoken interviewer question",
    "expected_concepts": ["concept 1", "concept 2"],
    "follow_ups": ["optional follow-up"]
}}
"""
        llm = AIFactory.get_llm_provider()
        try:
            res = await llm.generate_json(
                prompt=prompt,
                system_prompt=f"You are a seasoned technical hiring interviewer at {company.display_name} conducting a realistic, role-differentiated interview."
            )
            if isinstance(res, dict) and res.get("question_text"):
                return res
        except Exception:
            pass

        return cls.generate_deterministic_company_question(
            strategy=strategy,
            memory=memory,
            candidate_answer=candidate_answer
        )
