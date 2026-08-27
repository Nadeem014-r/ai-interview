"""Phase 8: Production-Grade Resume + Project Interrogation Engine.

Transforms candidate resume, projects, technologies, and statements into an
intelligent, progressive, adaptive interrogation graph that mirrors a real
senior technical interviewer exploring architecture, candidate ownership,
design decisions, trade-offs, security, scalability, and failure modes.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

from app.ai.factory import AIFactory
from app.interview.memory import InterviewMemory, ProjectMemory, CandidateClaim, MemoryManager


class InterrogationDepth(IntEnum):
    """Progressive interrogation depth levels (1 to 11)."""
    OVERVIEW = 1           # Problem & project overview
    OWNERSHIP = 2          # Candidate individual contribution & ownership
    IMPLEMENTATION = 3     # Concrete implementation mechanics
    ARCHITECTURE = 4       # System architecture & component interaction
    DESIGN_DECISIONS = 5   # Why technology X over Y
    TRADE_OFFS = 6         # Technical trade-offs & compromises
    SECURITY = 7           # Auth, tokens, validation, data protection
    PERFORMANCE = 8        # Caching, indexing, concurrency, async I/O
    SCALABILITY = 9        # 100 -> 10,000 users, bottlenecks, distribution
    FAILURE_MODES = 10     # Service downtime, network drop, race conditions
    PRODUCTION_READINESS = 11  # Observability, metrics, recovery, CI/CD


@dataclass
class ProjectClaimInvestigation:
    """Detailed investigation vector for a candidate's project claim."""
    project_name: str
    technology: str
    claim_text: str
    purpose: Optional[str] = None
    ownership_verified: bool = False
    current_depth: InterrogationDepth = InterrogationDepth.OVERVIEW
    discussed_hooks: List[str] = field(default_factory=list)
    unverified_hooks: List[str] = field(default_factory=list)
    security_probed: bool = False
    scalability_probed: bool = False
    failure_probed: bool = False
    tradeoffs_probed: bool = False


class ResumeProjectInterrogator:
    """
    Coordinates progressive, adaptive project and resume interrogation with
    dynamic depth adjustment based on candidate answers and demonstrated competence.
    """

    KNOWN_TECH_HOOKS: Dict[str, Dict[str, Any]] = {
        "fastapi": {
            "ownership": "What specific endpoints and backend services did you personally implement in FastAPI?",
            "architecture": "How did you structure the FastAPI routers, dependency injection, and data validation layers?",
            "tradeoffs": "Why did you choose FastAPI over alternatives like Django or Flask for this service?",
            "performance": "How did you handle async event loops and prevent blocking CPU-bound operations in FastAPI?",
            "failure": "How did you handle external API timeouts and exceptions gracefully without crashing endpoints?",
            "security": "How did you enforce request validation with Pydantic and secure your API against injection attacks?"
        },
        "postgresql": {
            "ownership": "Did you design the PostgreSQL database schema and write the migrations yourself?",
            "architecture": "How did you model the relationships between core entities and handle foreign key constraints?",
            "tradeoffs": "Why did you choose a relational database like PostgreSQL instead of a document store like MongoDB?",
            "performance": "What indexes did you create, and how did you verify that queries avoided full table scans?",
            "scalability": "If database read traffic increased tenfold, how would you optimize or scale PostgreSQL?",
            "failure": "How did you handle database connection pool exhaustion and transaction rollbacks during failures?"
        },
        "redis": {
            "ownership": "What specific data did you choose to cache in Redis, and what was your key naming strategy?",
            "architecture": "How did your application layer interact with Redis (cache-aside, write-through, or session store)?",
            "tradeoffs": "Why did you choose Redis over in-memory application caches or Memcached?",
            "performance": "How did you configure TTL expiration and memory eviction policies under memory pressure?",
            "failure": "What would happen to your system if Redis crashed or became temporarily unreachable?",
            "scalability": "How did you prevent cache stampedes (thundering herd) when high-traffic keys expired?"
        },
        "jwt": {
            "ownership": "How did you implement the JWT token generation, signing, and verification pipeline?",
            "architecture": "Where did the client store the token, and how did you structure access vs refresh tokens?",
            "tradeoffs": "Why did you use stateless JWTs instead of traditional server-side session cookies?",
            "security": "How did you protect against XSS and CSRF attacks, and how do you handle immediate token revocation?",
            "failure": "What happens if a user's permissions change while their access token is still valid?"
        },
        "docker": {
            "ownership": "Did you write the Dockerfiles and docker-compose configurations for the services?",
            "architecture": "How did you structure multi-stage builds and manage container networking?",
            "tradeoffs": "What trade-offs did containerization introduce in terms of build times and resource usage?",
            "production": "How did you manage environment variables and secrets inside Docker containers securely?"
        },
        "kafka": {
            "ownership": "What producers and consumer groups did you build in Kafka?",
            "architecture": "How did you partition topics and ensure message ordering?",
            "tradeoffs": "Why did you choose Kafka over lightweight queues like RabbitMQ or Redis Pub/Sub?",
            "failure": "How did you handle poison pill messages and consumer offset rebalancing during node failure?"
        },
        "react": {
            "ownership": "Which frontend modules and components did you personally build?",
            "architecture": "How did you manage state across components (Context, Redux, or Zustand)?",
            "performance": "How did you minimize unnecessary re-renders and optimize initial bundle load time?",
            "security": "How did you prevent client-side XSS vulnerabilities when rendering dynamic user data?"
        }
    }

    @classmethod
    def extract_structured_claims_from_resume(
        cls,
        resume_profile: Optional[Any],
        raw_text: Optional[str] = None
    ) -> List[CandidateClaim]:
        """
        Extracts verified structured claims from resume projects and skills
        without inventing unmentioned technologies.
        """
        claims: List[CandidateClaim] = []

        if not resume_profile:
            if raw_text:
                # Basic rule-based extraction from raw text
                for tech_key in cls.KNOWN_TECH_HOOKS.keys():
                    if re.search(rf"\b{re.escape(tech_key)}\b", raw_text, re.IGNORECASE):
                        claims.append(CandidateClaim(
                            claim_text=f"Experience with {tech_key.title()} in software projects",
                            topic="Technical Experience",
                            technology=tech_key.title()
                        ))
            return claims

        # Extract from structured projects
        projects = []
        if hasattr(resume_profile, "projects") and isinstance(resume_profile.projects, list):
            projects = resume_profile.projects
        elif isinstance(resume_profile, dict) and "projects" in resume_profile:
            projects = resume_profile.get("projects", [])

        for p in projects:
            if isinstance(p, dict):
                p_name = p.get("name") or p.get("title") or "Software Project"
                p_techs = p.get("technologies") or p.get("skills") or []
                p_desc = p.get("description") or ""

                tech_list = p_techs if isinstance(p_techs, list) else [str(p_techs)]
                for tech in tech_list:
                    claims.append(CandidateClaim(
                        claim_text=f"Used {tech} in project '{p_name}'",
                        topic="Project Architecture",
                        technology=tech,
                        project_name=p_name,
                        follow_up_hook=f"{tech} implementation details and architectural trade-offs in {p_name}"
                    ))

        # Extract from structured skills
        skills = []
        if hasattr(resume_profile, "skills") and isinstance(resume_profile.skills, list):
            skills = resume_profile.skills
        elif isinstance(resume_profile, dict) and "skills" in resume_profile:
            skills = resume_profile.get("skills", [])

        for s in skills[:8]:
            if not any(c.technology and c.technology.lower() == s.lower() for c in claims):
                claims.append(CandidateClaim(
                    claim_text=f"Proficient in {s}",
                    topic="Technical Proficiency",
                    technology=s,
                    follow_up_hook=f"Practical application and trade-offs of {s}"
                ))

        return claims

    @classmethod
    def identify_spontaneous_candidate_hooks(cls, answer_text: str) -> Optional[Dict[str, str]]:
        """
        Detects interesting spontaneously mentioned technical assertions in candidate answers
        (e.g., race conditions, bottlenecks, migrations, cache stampedes, deadlocks).
        """
        if not answer_text or not answer_text.strip():
            return None

        ans_lower = answer_text.lower()

        spontaneous_triggers = [
            (r"\brace condition\b", "race_condition", "You mentioned encountering a race condition. What caused it, and how did you debug and resolve it?"),
            (r"\bbottleneck\b", "bottleneck", "You mentioned identifying a bottleneck. How did you measure it, and what architectural change relieved it?"),
            (r"\bcache stampede\b|\bthundering herd\b", "cache_stampede", "You mentioned cache stampede. What caching pattern or locking mechanism did you put in place?"),
            (r"\bdeadlock\b", "deadlock", "You touched on deadlocks. How did you structure your database transactions to prevent concurrent deadlocks?"),
            (r"\bmigration\b", "migration", "You mentioned running a database migration. How did you ensure zero downtime and maintain backward compatibility?"),
            (r"\brate limit\b", "rate_limiting", "You mentioned rate limiting. Where was the rate limiter enforced, and what algorithm did you use?"),
            (r"\bmemory leak\b|\boom\b", "memory_leak", "You mentioned memory issues. How did you profile the memory consumption and identify the leak?"),
            (r"\bconnection pool\b", "connection_pool", "You mentioned connection pooling. How did you tune pool size and handle idle connection timeouts?")
        ]

        for pattern, hook_type, question_text in spontaneous_triggers:
            if re.search(pattern, ans_lower):
                return {
                    "hook_type": hook_type,
                    "question_text": question_text,
                    "expected_concepts": [hook_type.replace("_", " ").title(), "Root Cause Analysis", "Resolution Strategy"]
                }

        return None

    @classmethod
    def decide_progressive_interrogation_step(
        cls,
        memory: InterviewMemory,
        candidate_answer: str,
        last_eval_score: float,
        depth_score: float,
        current_project_name: Optional[str] = None
    ) -> Tuple[InterrogationDepth, str, Optional[str]]:
        """
        Determines the next progressive depth level, reasoning strategy, and target technology.
        Adapts dynamically based on answer strength, ownership verification, and conversation state.
        """
        ans_lower = (candidate_answer or "").lower()

        # Check for spontaneous hook first
        spontaneous = cls.identify_spontaneous_candidate_hooks(candidate_answer)
        if spontaneous:
            return InterrogationDepth.FAILURE_MODES, "spontaneous_hook", spontaneous["hook_type"]

        # Identify mentioned technologies
        techs_found = []
        for tech in cls.KNOWN_TECH_HOOKS.keys():
            if tech in ans_lower:
                techs_found.append(tech)

        target_tech = techs_found[0] if techs_found else None

        # Check if project ownership is already established
        project_mem = memory.projects.get(current_project_name) if current_project_name else None
        current_level = InterrogationDepth(project_mem.discussion_level + 1) if (project_mem and project_mem.discussion_level < 10) else InterrogationDepth.IMPLEMENTATION

        # Adaptive Escalation / Recovery based on answer quality
        if last_eval_score >= 8.0:
            # Strong candidate -> escalate to failure modes, trade-offs, security, or scale
            if current_level < InterrogationDepth.TRADE_OFFS:
                return InterrogationDepth.TRADE_OFFS, "strong_deep_dive_tradeoffs", target_tech
            elif current_level < InterrogationDepth.SCALABILITY:
                return InterrogationDepth.SCALABILITY, "strong_deep_dive_scale", target_tech
            elif current_level < InterrogationDepth.FAILURE_MODES:
                return InterrogationDepth.FAILURE_MODES, "strong_deep_dive_failure", target_tech
            else:
                return InterrogationDepth.PRODUCTION_READINESS, "strong_production_readiness", target_tech

        elif last_eval_score < 5.0 or depth_score < 5.0:
            # Weak or vague answer -> clarify ownership or fundamentals
            return InterrogationDepth.IMPLEMENTATION, "weak_clarify_fundamentals", target_tech

        else:
            # Normal progression
            return InterrogationDepth.DESIGN_DECISIONS, "normal_design_decisions", target_tech

    @classmethod
    def generate_deterministic_project_question(
        cls,
        memory: InterviewMemory,
        target_tech: Optional[str],
        depth_level: InterrogationDepth,
        reason: str,
        candidate_answer: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a natural, professional interviewer question tailored to project depth level
        with zero hallucinations.
        """
        tech_key = (target_tech or "fastapi").lower()
        hooks = cls.KNOWN_TECH_HOOKS.get(tech_key, cls.KNOWN_TECH_HOOKS["fastapi"])
        p_title = project_name or "your project"

        # Check for spontaneous hook in answer
        spontaneous = cls.identify_spontaneous_candidate_hooks(candidate_answer)
        if spontaneous:
            return {
                "question_text": spontaneous["question_text"],
                "expected_concepts": spontaneous["expected_concepts"],
                "follow_ups": ["How did you verify the fix in production?"]
            }

        # Level 2: Ownership verification
        if depth_level == InterrogationDepth.OWNERSHIP or "ownership" in reason:
            return {
                "question_text": f"In {p_title}, what specific technical components and backend services did you personally design and implement versus the rest of the team?",
                "expected_concepts": ["Individual contribution", "Component ownership", "Architecture boundaries"],
                "follow_ups": ["What was the most challenging technical decision you owned?"]
            }

        # Level 5: Design decisions
        elif depth_level == InterrogationDepth.DESIGN_DECISIONS:
            if "tradeoffs" in hooks:
                return {
                    "question_text": f"Looking at {p_title}, why did you choose {tech_key.title()} for this architecture, and what alternative solutions did you consider?",
                    "expected_concepts": [f"Rationale for {tech_key.title()}", "Alternatives considered", "Architectural trade-offs"],
                    "follow_ups": ["What trade-offs did that decision introduce?"]
                }
            return {
                "question_text": f"What was the key architectural rationale behind choosing your tech stack for {p_title}?",
                "expected_concepts": ["Design rationale", "Technology trade-offs"],
                "follow_ups": ["How did that decision hold up as the project grew?"]
            }

        # Level 6: Technical Trade-offs
        elif depth_level == InterrogationDepth.TRADE_OFFS:
            if tech_key == "redis":
                return {
                    "question_text": "When implementing caching with Redis, what trade-offs did you make between data freshness and read latency?",
                    "expected_concepts": ["Cache consistency", "TTL vs Invalidation", "Read latency"],
                    "follow_ups": ["How did you prevent stale data reads?"]
                }
            elif tech_key == "postgresql" or tech_key == "postgres":
                return {
                    "question_text": "How did you balance index coverage for read queries against the write amplification and storage overhead on PostgreSQL?",
                    "expected_concepts": ["Index overhead", "Write amplification", "Query execution plan"],
                    "follow_ups": ["When did you decide not to add an index?"]
                }
            elif tech_key == "jwt":
                return {
                    "question_text": "Since JWTs are stateless, what trade-offs did you accept regarding token revocation and immediate permission updates?",
                    "expected_concepts": ["Statelessness vs revocation", "Token lifetime", "Blocklist trade-offs"],
                    "follow_ups": ["How did you mitigate that trade-off?"]
                }
            else:
                return {
                    "question_text": f"What were the primary architectural trade-offs you had to navigate when designing {p_title}?",
                    "expected_concepts": ["Technical trade-offs", "Complexity vs Maintainability"],
                    "follow_ups": ["What would you design differently in hindsight?"]
                }

        # Level 7: Security
        elif depth_level == InterrogationDepth.SECURITY:
            if "security" in hooks:
                return {
                    "question_text": hooks["security"],
                    "expected_concepts": ["Security controls", "Vulnerability mitigation", "Access verification"],
                    "follow_ups": ["How did you test for potential security vulnerabilities?"]
                }
            return {
                "question_text": f"How did you secure your endpoints and validate untrusted candidate/user inputs in {p_title}?",
                "expected_concepts": ["Input validation", "Authentication/Authorization", "Sanitization"],
                "follow_ups": ["How did you manage API secrets and keys?"]
            }

        # Level 9: Scalability
        elif depth_level == InterrogationDepth.SCALABILITY:
            if tech_key == "postgresql" or tech_key == "postgres":
                return {
                    "question_text": "Suppose your database traffic grew from 100 concurrent users to 10,000 concurrent users. Where would PostgreSQL bottleneck first, and how would you optimize it?",
                    "expected_concepts": ["Connection pooling", "Read replicas", "Indexing and query optimization"],
                    "follow_ups": ["How would you handle write contention?"]
                }
            elif tech_key == "redis":
                return {
                    "question_text": "Under high concurrency, how did you protect your Redis cache and database against cache stampede and memory exhaustion?",
                    "expected_concepts": ["Cache stampede mitigation", "Mutex locks / probabilistic early expiration", "Eviction policies"],
                    "follow_ups": ["How would you partition or cluster Redis if data exceeded a single node?"]
                }
            else:
                return {
                    "question_text": f"If concurrent traffic to {p_title} increased by a factor of 50x, what component would bottleneck first, and how would you scale it?",
                    "expected_concepts": ["Bottleneck identification", "Horizontal scaling", "Concurrency management"],
                    "follow_ups": ["How would you verify this under load testing?"]
                }

        # Level 10: Failure Modes & Resiliency
        elif depth_level == InterrogationDepth.FAILURE_MODES:
            if "failure" in hooks:
                return {
                    "question_text": hooks["failure"],
                    "expected_concepts": ["Failure mode handling", "Graceful degradation", "Error recovery"],
                    "follow_ups": ["How do you monitor and alert on this in production?"]
                }
            return {
                "question_text": f"What happens in {p_title} if a critical dependency or downstream database service goes down or experiences a network partition?",
                "expected_concepts": ["Circuit breaking", "Graceful degradation", "Retry mechanisms with backoff"],
                "follow_ups": ["How do you ensure data integrity during partial failures?"]
            }

        # Level 11: Production Readiness
        elif depth_level == InterrogationDepth.PRODUCTION_READINESS:
            return {
                "question_text": f"How did you instrument {p_title} for observability, metrics collection, and production error alerting?",
                "expected_concepts": ["Structured logging", "Metrics & latency tracking", "Health checks & alerts"],
                "follow_ups": ["What was your strategy for zero-downtime deployments?"]
            }

        # Default fallback implementation question
        return {
            "question_text": f"Can you walk me through the concrete implementation details of {tech_key.title()} in {p_title} and how it interacts with the rest of your system?",
            "expected_concepts": ["Component integration", "Implementation mechanics", "Data flow"],
            "follow_ups": ["What technical challenge was hardest to solve during implementation?"]
        }

    @classmethod
    async def generate_adaptive_project_question(
        cls,
        memory: InterviewMemory,
        candidate_answer: str,
        last_eval_score: float,
        depth_score: float,
        target_level: str = "entry",
        current_project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an adaptive, highly contextual project interrogation question using LLM
        with prioritized Structured Memory context, with reliable deterministic fallback.
        """
        depth_level, reason, target_tech = cls.decide_progressive_interrogation_step(
            memory=memory,
            candidate_answer=candidate_answer,
            last_eval_score=last_eval_score,
            depth_score=depth_score,
            current_project_name=current_project_name
        )

        llm = AIFactory.get_llm_provider()
        memory_context = MemoryManager.get_structured_llm_context(memory, max_recent_turns=3)

        prompt = f"""
You are an expert senior engineering interviewer conducting an in-depth technical interrogation of a candidate's resume and software projects for a {target_level} role.

STRUCTURED INTERVIEW MEMORY & PROJECT CLAIMS:
{memory_context}

CANDIDATE'S LATEST ANSWER:
<CANDIDATE_ANSWER>
{candidate_answer}
</CANDIDATE_ANSWER>

INTERROGATION DIRECTIVE:
- Target Depth Level: Level {depth_level.value} ({depth_level.name})
- Strategy / Reason: {reason}
- Target Technology/Component: {target_tech or "Architecture"}
- Project Focus: {current_project_name or "Candidate Project"}

PREVIOUSLY ASKED QUESTIONS (DO NOT DUPLICATE OR PARAPHRASE):
{memory.asked_question_texts[-4:] if memory.asked_question_texts else "None"}

INSTRUCTIONS:
1. Ask ONE clear, sharp, conversational interviewer question.
2. Build naturally on what the candidate actually claimed. Use natural transitions ("You mentioned...", "Looking at the architecture for...", "Going back to...").
3. DO NOT use robotic phrasing like "According to claim #2" or "Memory indicates".
4. DO NOT ask multiple combined questions in one prompt. Ask ONE primary question.
5. If testing scalability or failure modes, ground it in the candidate's actual technologies (e.g. PostgreSQL, Redis, FastAPI, JWT).
6. DO NOT invent unmentioned technologies that the candidate never claimed.
7. If candidate gave a strong answer, probe into edge cases, distributed failure modes, or trade-offs.
8. If candidate gave a weak answer, ask a clarifying question about core mechanics.

Return JSON:
{{
    "question_text": "The single conversational interviewer question",
    "expected_concepts": ["concept 1", "concept 2"],
    "follow_ups": ["optional subsequent probe"]
}}
"""
        try:
            res = await llm.generate_json(
                prompt=prompt,
                system_prompt="You are a seasoned human technical hiring interviewer conducting deep, realistic resume and project interrogations."
            )
            if isinstance(res, dict) and res.get("question_text"):
                return res
        except Exception:
            pass

        return cls.generate_deterministic_project_question(
            memory=memory,
            target_tech=target_tech,
            depth_level=depth_level,
            reason=reason,
            candidate_answer=candidate_answer,
            project_name=current_project_name
        )
