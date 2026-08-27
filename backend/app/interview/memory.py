"""Phase 7: Human-Like Structured Interview Memory & Adaptive Follow-Up Engine.

Maintains multi-turn structured memory of candidate profile, resume claims,
project implementations, technologies, conversation turns, demonstrated strengths,
weaknesses, and follow-up opportunities to enable authentic, connected,
non-repetitive conversational interviewing.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CandidateClaim:
    """A specific technical assertion or project responsibility claimed by candidate."""
    claim_text: str
    topic: str
    technology: Optional[str] = None
    project_name: Optional[str] = None
    source_turn: int = 1
    verified: bool = False
    verification_depth: int = 0
    follow_up_hook: Optional[str] = None


@dataclass
class ProjectMemory:
    """Detailed memory of a candidate's software project."""
    name: str
    technologies: List[str] = field(default_factory=list)
    description: Optional[str] = None
    responsibilities: List[str] = field(default_factory=list)
    architecture_details: List[str] = field(default_factory=list)
    challenges_mentioned: List[str] = field(default_factory=list)
    discussion_level: int = 0  # 0=unexplored, 1=overview, 2=implementation, 3=deep trade-offs
    claims: List[str] = field(default_factory=list)


@dataclass
class FollowUpOpportunity:
    """A queued opportunity for the interviewer to probe or clarify."""
    topic: str
    target_claim: str
    reason: str  # e.g., 'probe_claim', 'clarify_vague', 'misconception', 'deep_dive_scale'
    suggested_probe: str
    priority: int = 1  # 1=high, 2=medium, 3=low
    related_tech: Optional[str] = None


@dataclass
class ConversationTurnMemory:
    """Compact summary of a completed question-answer turn."""
    turn_index: int
    question_text: str
    candidate_answer: str
    topic: str
    score: float
    key_technologies: List[str] = field(default_factory=list)
    demonstrated_concepts: List[str] = field(default_factory=list)
    missing_concepts: List[str] = field(default_factory=list)
    misconceptions: List[str] = field(default_factory=list)
    extracted_claim: Optional[str] = None


@dataclass
class InterviewMemory:
    """
    Comprehensive structured memory of the entire interview session.
    Preserves candidate profile, resume claims, conversation history,
    topic mastery, and follow-up opportunities.
    """
    interview_id: int
    candidate_profile: Dict[str, Any] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    projects: Dict[str, ProjectMemory] = field(default_factory=dict)
    claims: List[CandidateClaim] = field(default_factory=list)
    conversation_turns: List[ConversationTurnMemory] = field(default_factory=list)
    covered_topics: List[str] = field(default_factory=list)
    topic_question_counts: Dict[str, int] = field(default_factory=dict)
    strong_topics: List[str] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)
    unexplored_topics: List[str] = field(default_factory=list)
    follow_up_queue: List[FollowUpOpportunity] = field(default_factory=list)
    asked_question_texts: List[str] = field(default_factory=list)
    active_project_focus: Optional[str] = None


class MemoryManager:
    """Orchestrates memory extraction, updating, context window prioritization, and retrieval."""

    KNOWN_TECH_PATTERNS = [
        "fastapi", "flask", "django", "react", "next.js", "nextjs", "vue", "angular",
        "nodejs", "node.js", "express", "postgresql", "postgres", "mysql", "mongodb",
        "redis", "kafka", "rabbitmq", "docker", "kubernetes", "k8s", "aws", "gcp",
        "azure", "jwt", "oauth", "graphql", "rest api", "grpc", "pydantic", "sqlalchemy",
        "gemini", "openai", "pytorch", "tensorflow", "scikit-learn", "b-tree", "hash table",
        "elasticsearch", "celery", "webrtc", "websockets", "microservices", "git"
    ]

    @classmethod
    def build_initial_memory(
        cls,
        interview_id: int,
        role_key_topics: List[str],
        resume_profile: Optional[Any] = None,
        candidate_profile_dict: Optional[Dict[str, Any]] = None
    ) -> InterviewMemory:
        """Initializes structured interview memory from resume and role rubric."""
        skills = []
        projects_dict: Dict[str, ProjectMemory] = {}
        claims: List[CandidateClaim] = []

        if resume_profile:
            # Ingest resume skills
            if hasattr(resume_profile, "skills") and isinstance(resume_profile.skills, list):
                skills.extend(resume_profile.skills)
            elif isinstance(resume_profile, dict) and "skills" in resume_profile:
                skills.extend(resume_profile.get("skills", []))

            # Ingest resume projects
            res_projects = []
            if hasattr(resume_profile, "projects") and isinstance(resume_profile.projects, list):
                res_projects = resume_profile.projects
            elif isinstance(resume_profile, dict) and "projects" in resume_profile:
                res_projects = resume_profile.get("projects", [])

            for p in res_projects:
                if isinstance(p, dict):
                    p_name = p.get("name") or p.get("title") or "Software Project"
                    p_tech = p.get("technologies") or p.get("skills") or []
                    p_desc = p.get("description") or ""
                    projects_dict[p_name] = ProjectMemory(
                        name=p_name,
                        technologies=p_tech if isinstance(p_tech, list) else [str(p_tech)],
                        description=p_desc,
                        discussion_level=0
                    )
                    claims.append(CandidateClaim(
                        claim_text=f"Built project '{p_name}' using {', '.join(p_tech[:4]) if p_tech else 'modern stack'}",
                        topic="Project Experience",
                        project_name=p_name
                    ))

        return InterviewMemory(
            interview_id=interview_id,
            candidate_profile=candidate_profile_dict or {},
            skills=list(set(skills)),
            projects=projects_dict,
            claims=claims,
            unexplored_topics=list(role_key_topics or []),
            topic_question_counts={t: 0 for t in (role_key_topics or [])}
        )

    @classmethod
    def extract_technical_entities_and_claims(
        cls,
        answer_text: str,
        question_text: str,
        topic: str,
        turn_index: int
    ) -> Tuple[List[str], Optional[CandidateClaim]]:
        """Extracts mentioned technical tools, frameworks, and specific candidate assertions."""
        if not answer_text or not answer_text.strip():
            return [], None

        ans_lower = answer_text.lower()
        extracted_tech: List[str] = []

        for tech in cls.KNOWN_TECH_PATTERNS:
            # Word boundary search for accurate tool identification
            pattern = rf"\b{re.escape(tech)}\b"
            if re.search(pattern, ans_lower):
                extracted_tech.append(tech.title() if len(tech) > 4 else tech.upper())

        # Identify high-value candidate assertions
        claim_obj: Optional[CandidateClaim] = None
        claim_triggers = [
            r"(?:i (?:used|built|implemented|created|designed|deployed|developed))\s+([^.!?\n]+)",
            r"(?:we (?:used|built|implemented|created|designed))\s+([^.!?\n]+)",
            r"(?:in my (?:project|backend|frontend|system))\s*[,:]?\s*([^.!?\n]+)",
            r"(?:for (?:caching|authentication|storage|indexing))\s*[,:]?\s*(?:i used|we used)\s+([^.!?\n]+)"
        ]

        for trig in claim_triggers:
            match = re.search(trig, ans_lower, re.IGNORECASE)
            if match:
                raw_claim = match.group(0).strip()
                if len(raw_claim) > 10:
                    primary_tech = extracted_tech[0] if extracted_tech else None
                    hook = None
                    if "redis" in raw_claim or "caching" in raw_claim:
                        hook = "cache invalidation and eviction policies"
                    elif "fastapi" in raw_claim:
                        hook = "asynchronous request handling and concurrency"
                    elif "postgres" in raw_claim or "postgresql" in raw_claim:
                        hook = "database schema relationships and indexing"
                    elif "jwt" in raw_claim or "auth" in raw_claim:
                        hook = "token expiration, refresh mechanisms, and signature verification"
                    elif "kafka" in raw_claim:
                        hook = "partitioning and consumer group offset management"

                    claim_obj = CandidateClaim(
                        claim_text=raw_claim.capitalize(),
                        topic=topic,
                        technology=primary_tech,
                        source_turn=turn_index,
                        follow_up_hook=hook
                    )
                    break

        return extracted_tech, claim_obj

    @classmethod
    def ingest_turn(
        cls,
        memory: InterviewMemory,
        question_text: str,
        candidate_answer: str,
        eval_dict: Dict[str, Any],
        topic: str
    ) -> None:
        """Updates structured memory with new answer turn facts, claims, and evaluation."""
        turn_index = len(memory.conversation_turns) + 1
        extracted_tech, new_claim = cls.extract_technical_entities_and_claims(
            candidate_answer, question_text, topic, turn_index
        )

        demonstrated = eval_dict.get("demonstrated_concepts", []) if eval_dict else []
        missing = eval_dict.get("missing_concepts", []) if eval_dict else []
        misconceptions = eval_dict.get("misconceptions", []) if eval_dict else []
        score = float(eval_dict.get("overall_question_score", 6.0)) if eval_dict else 6.0
        depth_score = float(eval_dict.get("depth_score", 6.0)) if eval_dict else 6.0

        if new_claim:
            memory.claims.append(new_claim)

        # Record conversation turn
        turn_mem = ConversationTurnMemory(
            turn_index=turn_index,
            question_text=question_text,
            candidate_answer=candidate_answer,
            topic=topic,
            score=score,
            key_technologies=extracted_tech,
            demonstrated_concepts=demonstrated,
            missing_concepts=missing,
            misconceptions=misconceptions,
            extracted_claim=new_claim.claim_text if new_claim else None
        )
        memory.conversation_turns.append(turn_mem)
        memory.asked_question_texts.append(question_text)

        # Track topic question counts & coverage
        memory.topic_question_counts[topic] = memory.topic_question_counts.get(topic, 0) + 1
        if topic not in memory.covered_topics:
            memory.covered_topics.append(topic)
        if topic in memory.unexplored_topics:
            memory.unexplored_topics.remove(topic)

        # Update mastery categories
        if score >= 8.0:
            if topic not in memory.strong_topics:
                memory.strong_topics.append(topic)
            if topic in memory.weak_topics:
                memory.weak_topics.remove(topic)
        elif score < 5.0:
            if topic not in memory.weak_topics:
                memory.weak_topics.append(topic)
            if topic in memory.strong_topics:
                memory.strong_topics.remove(topic)

        # Update or create project details if project was discussed
        ans_lower = candidate_answer.lower()
        for p_name, p_mem in memory.projects.items():
            if p_name.lower() in ans_lower or any(t.lower() in ans_lower for t in p_mem.technologies):
                p_mem.discussion_level += 1
                for tech in extracted_tech:
                    if tech not in p_mem.technologies:
                        p_mem.technologies.append(tech)

        # Queue follow-up opportunities
        if new_claim and new_claim.follow_up_hook:
            memory.follow_up_queue.insert(0, FollowUpOpportunity(
                topic=topic,
                target_claim=new_claim.claim_text,
                reason="probe_claim",
                suggested_probe=f"You mentioned {new_claim.claim_text}. How did you handle {new_claim.follow_up_hook}?",
                priority=1,
                related_tech=new_claim.technology
            ))
        elif misconceptions:
            memory.follow_up_queue.insert(0, FollowUpOpportunity(
                topic=topic,
                target_claim=candidate_answer[:80],
                reason="clarify_misconception",
                suggested_probe=f"Let's clarify {misconceptions[0]}. What happens under the hood?",
                priority=1
            ))
        elif depth_score < 5.5 and score >= 4.0:
            memory.follow_up_queue.append(FollowUpOpportunity(
                topic=topic,
                target_claim=candidate_answer[:80],
                reason="clarify_vague",
                suggested_probe=f"You touched on {topic}. Can you walk through a concrete implementation example?",
                priority=2
            ))
        elif score >= 8.0:
            memory.follow_up_queue.append(FollowUpOpportunity(
                topic=topic,
                target_claim=candidate_answer[:80],
                reason="deep_dive_scale",
                suggested_probe=f"Under high load or failure scenarios with {topic}, what trade-offs emerge?",
                priority=2
            ))

    @classmethod
    def get_structured_llm_context(
        cls,
        memory: InterviewMemory,
        max_recent_turns: int = 3
    ) -> str:
        """
        Builds prioritized, token-efficient structured interview context for Gemini.
        Prioritizes: candidate profile, project claims, mastery state, recent turns.
        """
        sections: List[str] = []

        # 1. Candidate & Skills Profile
        if memory.skills:
            sections.append(f"CANDIDATE KNOWN SKILLS: {', '.join(memory.skills[:10])}")

        # 2. Key Projects & Claims
        project_summaries = []
        for p_name, p in list(memory.projects.items())[:3]:
            tech_str = f" (Tech: {', '.join(p.technologies[:4])})" if p.technologies else ""
            project_summaries.append(f"- Project: {p_name}{tech_str} [Level: {p.discussion_level}]")
        if project_summaries:
            sections.append("KEY PROJECTS IN MEMORY:\n" + "\n".join(project_summaries))

        # 3. Specific Candidate Technical Claims
        recent_claims = memory.claims[-4:] if memory.claims else []
        if recent_claims:
            claim_lines = [f"- Claim: \"{c.claim_text}\" (Topic: {c.topic})" for c in recent_claims]
            sections.append("SPECIFIC CANDIDATE CLAIMS TO PROBE/REMEMBER:\n" + "\n".join(claim_lines))

        # 4. Topic Coverage & Strengths/Weaknesses
        covered_str = f"Covered: {', '.join(memory.covered_topics)}" if memory.covered_topics else "None"
        strong_str = f"Strong: {', '.join(memory.strong_topics)}" if memory.strong_topics else "None"
        weak_str = f"Weak/Misconceptions: {', '.join(memory.weak_topics)}" if memory.weak_topics else "None"
        sections.append(f"TOPIC PROGRESSION:\n- {covered_str}\n- {strong_str}\n- {weak_str}")

        # 5. Recent Conversation Turns (Question + Answer)
        recent_turns = memory.conversation_turns[-max_recent_turns:] if memory.conversation_turns else []
        if recent_turns:
            turn_lines = []
            for t in recent_turns:
                turn_lines.append(f"- Q{t.turn_index} ({t.topic}): {t.question_text}\n  Answer: \"{t.candidate_answer[:220]}\" (Score: {t.score}/10)")
            sections.append("RECENT CONVERSATION HISTORY:\n" + "\n".join(turn_lines))

        return "\n\n".join(sections)

    @classmethod
    def is_semantic_duplicate(
        cls,
        candidate_question: str,
        memory: InterviewMemory,
        similarity_threshold: float = 0.72
    ) -> bool:
        """
        Detects lexical and semantic repetition against all previously asked questions.
        """
        if not candidate_question or not memory.asked_question_texts:
            return False

        clean_cand = re.sub(r'[^\w\s]', '', candidate_question.lower()).split()
        cand_set = set(clean_cand)
        if not cand_set:
            return False

        for asked in memory.asked_question_texts:
            clean_asked = re.sub(r'[^\w\s]', '', asked.lower()).split()
            asked_set = set(clean_asked)
            if not asked_set:
                continue

            # Exact match
            if clean_cand == clean_asked:
                return True

            # Jaccard lexical overlap
            overlap = len(cand_set.intersection(asked_set)) / float(max(len(cand_set), len(asked_set)))
            if overlap >= similarity_threshold:
                return True

            # Substring containment for long questions
            str_cand = " ".join(clean_cand)
            str_asked = " ".join(clean_asked)
            if len(str_cand) > 35 and (str_cand in str_asked or str_asked in str_cand):
                return True

        return False
