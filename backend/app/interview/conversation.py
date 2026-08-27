"""Phase 7: Conversational Follow-Up & Adaptive Probing Intelligence.

Decides when and how an experienced interviewer should probe an answer deeper,
distinguishing vague answers, strong answers, technical misconceptions, partial answers,
and specific candidate assertions using Structured Interview Memory.
"""

from typing import Dict, Any, Optional, List, Tuple
import re
from app.ai.factory import AIFactory
from app.interview.memory import InterviewMemory, MemoryManager
from app.interview.project_interrogator import ResumeProjectInterrogator, InterrogationDepth


class FollowUpEngine:
    """Evaluates candidate answer depth and generates human-like follow-up probes with memory."""

    @staticmethod
    def should_follow_up(
        last_eval_score: float,
        evidence: List[str],
        depth_score: float,
        turn_count_on_topic: int = 1,
        time_remaining_seconds: int = 600,
        candidate_answer: Optional[str] = None,
        last_eval_dict: Optional[Dict[str, Any]] = None,
        topic: str = "",
        memory: Optional[InterviewMemory] = None
    ) -> Tuple[bool, str]:
        """
        Determines whether to ask a follow-up question on the current topic or advance to a new topic.
        Returns (should_probe: bool, reason_category: str).
        """
        # If very little time remains (< 2.5 minutes), avoid opening a deep follow-up
        if time_remaining_seconds < 150:
            return False, "time_constrained"

        # Do not stay on the same topic for more than 2 consecutive follow-ups
        if turn_count_on_topic >= 3:
            return False, "topic_budget_exhausted"

        ans_lower = (candidate_answer or "").lower() if candidate_answer else ""
        is_idontknow = bool(candidate_answer and any(kw in ans_lower for kw in [
            "don't know", "dont know", "no idea", "not sure", "pass", "skip", "no clue"
        ]))

        is_intro_hr = any(w in (topic or "").lower() for w in ["introduction", "motivation", "background", "teamwork", "leadership"])

        # HR / Introduction: Once candidate gives a satisfactory intro, advance to technical core competencies
        if is_intro_hr and last_eval_score >= 6.5:
            return False, "advance_topic"

        # Case 1: "I don't know" on turn 1 -> give one simpler foundational probe if turn 1
        if is_idontknow and turn_count_on_topic == 1:
            return True, "i_dont_know_foundation"
        elif is_idontknow:
            return False, "advance_topic"

        # Check explicit recommended_action or misconceptions from evaluator if available
        if last_eval_dict:
            misconceptions = last_eval_dict.get("misconceptions", [])
            rec_action = last_eval_dict.get("recommended_action", "")
            if misconceptions and turn_count_on_topic == 1:
                return True, "clarify_misconception"
            if rec_action in ["drill_deep", "deepen"] and turn_count_on_topic == 1:
                return True, "strong_answer_tradeoffs"
            if rec_action in ["probe_missing", "follow_up"] and turn_count_on_topic == 1:
                return True, "vague_answer" if depth_score < 5.5 else "clarify_concept"
            if rec_action in ["recover", "recover_foundation"] and turn_count_on_topic == 1:
                return True, "clarify_misconception" if last_eval_score < 4.5 else "i_dont_know_foundation"

        # Case 2: Technical misconception detected (score < 4.5 and mentions technical claim)
        has_misconception = bool(candidate_answer and any(pattern in ans_lower for pattern in [
            "jwt is encrypted", "no garbage collector", "malloc", "indexes are encrypted"
        ]))
        if (has_misconception or last_eval_score < 4.5) and turn_count_on_topic == 1:
            return True, "clarify_misconception"

        # Case 3: Specific candidate claim in memory with unprobed hook
        if memory and memory.claims:
            latest_claim = memory.claims[-1]
            if latest_claim.follow_up_hook and turn_count_on_topic == 1:
                return True, "probe_candidate_claim"

        # Case 4: Vague / Low-depth answer on first attempt -> probe for specifics
        if depth_score < 6.0 and turn_count_on_topic == 1:
            return True, "vague_answer"

        # Case 5: High score / strong answer -> probe for architectural trade-offs, scale, failure modes
        if last_eval_score >= 8.0 and turn_count_on_topic == 1:
            return True, "strong_answer_tradeoffs"

        # Case 6: Borderline partial understanding (5.0 <= score < 6.8) -> clarify missing trade-off
        if 5.0 <= last_eval_score < 6.8 and turn_count_on_topic == 1:
            return True, "clarify_concept"

        return False, "advance_topic"

    @staticmethod
    def generate_deterministic_follow_up(
        topic: str,
        reason_category: str,
        candidate_answer: str,
        target_level: str = "entry",
        eval_dict: Optional[Dict[str, Any]] = None,
        asked_texts: Optional[List[str]] = None,
        memory: Optional[InterviewMemory] = None
    ) -> Dict[str, Any]:
        """
        Deterministic follow-up generator grounded in answer details, candidate claims,
        and missing concepts with zero hallucinations.
        """
        ans_lower = (candidate_answer or "").lower()
        asked = asked_texts or []
        if memory and memory.asked_question_texts:
            asked = list(set(asked + memory.asked_question_texts))

        is_hr_topic = any(w in topic.lower() for w in ["introduction", "motivation", "background", "teamwork", "leadership", "strength", "behavioral"])

        # 0. Candidate Claim-Driven Memory Follow-Ups
        if (reason_category == "probe_candidate_claim" or (memory and memory.claims)) and not is_hr_topic:
            # Check for Redis caching assertion
            if "redis" in ans_lower or (memory and any("redis" in c.claim_text.lower() for c in memory.claims[-2:])):
                return {
                    "question_text": "You mentioned using Redis for caching to reduce repeated database queries. What specific data did you choose to cache, and how did you handle cache invalidation and cache stampede scenarios?",
                    "expected_concepts": ["Cache invalidation strategies", "Cache stampede / TTL", "Cache-aside vs write-through"],
                    "follow_ups": ["How did you monitor cache hit rates and handle cache eviction under memory pressure?"]
                }
            # Check for FastAPI + PostgreSQL / SQLite assertion
            elif ("fastapi" in ans_lower and "postgres" in ans_lower) or (memory and any("fastapi" in c.claim_text.lower() and "postgres" in c.claim_text.lower() for c in memory.claims[-2:])):
                return {
                    "question_text": "You mentioned using FastAPI with PostgreSQL for storing interview sessions. How did you design the database relationships, and how did you handle asynchronous database sessions with SQLAlchemy?",
                    "expected_concepts": ["PostgreSQL schema design", "Async database sessions", "SQLAlchemy async engine"],
                    "follow_ups": ["How did you manage connection pooling under concurrent traffic?"]
                }
            elif "fastapi" in ans_lower or (memory and any("fastapi" in c.claim_text.lower() for c in memory.claims[-2:])):
                return {
                    "question_text": "You mentioned that you worked extensively with FastAPI. Can you walk me through how you handled asynchronous request processing and concurrency in your endpoints?",
                    "expected_concepts": ["FastAPI ASGI architecture", "Async concurrency", "Pydantic validation"],
                    "follow_ups": ["How do you handle CPU-bound vs I/O-bound tasks in FastAPI?"]
                }
            elif "jwt" in ans_lower or (memory and any("jwt" in c.claim_text.lower() for c in memory.claims[-2:])):
                return {
                    "question_text": "You mentioned implementing JWT authentication. Where did you store the token on the client side, and how did you handle token expiration and refresh token rotation?",
                    "expected_concepts": ["Token storage (HttpOnly cookies vs localStorage)", "Refresh token rotation", "Signature verification"],
                    "follow_ups": ["What security mechanisms prevent XSS and CSRF attacks when using JWTs?"]
                }
            elif "postgres" in ans_lower or "postgresql" in ans_lower or "database" in ans_lower:
                return {
                    "question_text": "You mentioned using PostgreSQL for persistent data storage. How did you structure your indexes to optimize query performance, and what trade-offs did that introduce on write operations?",
                    "expected_concepts": ["B-Tree indexing", "Query execution plans", "Write amplification"],
                    "follow_ups": ["How do you detect slow queries using EXPLAIN ANALYZE?"]
                }

        # 1. HR / Behavioral Follow-Ups
        if is_hr_topic:
            if reason_category in ["recover", "i_dont_know_foundation"]:
                candidates = [
                    {
                        "question_text": "What interests you about this role, and can you walk me through one project that is relevant to the work you'd be doing here?",
                        "expected_concepts": ["Role alignment", "Relevant project experience"],
                        "follow_ups": ["What specific technical challenges did you solve in that project?"]
                    },
                    {
                        "question_text": "To start off, could you summarize your background and what motivated you to pursue software engineering?",
                        "expected_concepts": ["Educational background", "Career motivation"],
                        "follow_ups": ["Which areas of software engineering excite you most?"]
                    }
                ]
            elif "react" in ans_lower or "python" in ans_lower or "node" in ans_lower or "fastapi" in ans_lower:
                tech = "React" if "react" in ans_lower else ("FastAPI" if "fastapi" in ans_lower else ("Python" if "python" in ans_lower else "your stack"))
                candidates = [
                    {
                        "question_text": f"You mentioned working with {tech}. What part of that project did you personally implement, and what was the most challenging technical decision you made?",
                        "expected_concepts": ["Individual contribution", "Technical decision making", "Problem solving"],
                        "follow_ups": ["How did you verify that your solution met performance and quality standards?"]
                    }
                ]
            else:
                candidates = [
                    {
                        "question_text": "Could you walk me through a key software project you've worked on recently and explain your specific role in building it?",
                        "expected_concepts": ["Project walkthrough", "Individual ownership", "Architectural choices"],
                        "follow_ups": ["What was the most challenging bug or architectural decision in that project?"]
                    }
                ]

            for cand in candidates:
                if not any(cand["question_text"].lower() == a.lower() for a in asked):
                    return cand
            return candidates[0]

        # 2. Misconception Probing
        if reason_category == "clarify_misconception":
            candidates = [
                {
                    "question_text": f"Let's clarify the mechanics of {topic}. What actually happens under the hood during execution, and how does the system maintain correctness?",
                    "expected_concepts": [f"Accurate mechanics of {topic}", "Runtime behavior", "Operational constraints"],
                    "follow_ups": ["What trade-offs or edge-case constraints apply here?"]
                },
                {
                    "question_text": f"Looking at your explanation of {topic}, how does the engine verify state and maintain consistency under edge conditions?",
                    "expected_concepts": ["State verification", "Consistency guarantees", "Error handling"],
                    "follow_ups": ["What would happen if an invalid input or failure occurred?"]
                }
            ]
            if "jwt" in ans_lower or "jwt" in topic.lower():
                candidates.insert(0, {
                    "question_text": "What information is encoded inside the payload of a JWT, and what mechanism ensures it cannot be altered without detection?",
                    "expected_concepts": ["Payload encoding vs encryption", "Cryptographic signing", "Signature verification"],
                    "follow_ups": ["Where should the signing secret or public key be kept?"]
                })
            elif "hash" in ans_lower or "hash" in topic.lower():
                candidates.insert(0, {
                    "question_text": "What ensures average O(1) time complexity in hash tables, and under what specific circumstances can lookups degrade?",
                    "expected_concepts": ["Hash distribution", "Collision resolution", "Worst-case complexity O(N)"],
                    "follow_ups": ["How does load factor trigger resizing?"]
                })
            elif "index" in ans_lower or "database" in ans_lower or "sql" in topic.lower():
                candidates.insert(0, {
                    "question_text": "You mentioned indexes improve performance. Can you explain what actually happens when the database engine uses an index to locate rows?",
                    "expected_concepts": ["B-Tree traversal", "Disk I/O reduction", "Write amplification"],
                    "follow_ups": ["When would a sequential scan be chosen over an index scan?"]
                })

            for cand in candidates:
                if not any(cand["question_text"].lower() == a.lower() for a in asked):
                    return cand
            return candidates[0]

        # 3. Evasive / I Don't Know / Foundation Recovery
        elif reason_category in ["i_dont_know_foundation", "recover"]:
            candidates = [
                {
                    "question_text": f"That's completely fine. Let's look at {topic} from the fundamentals. At a high level, what is the core problem that {topic} is designed to solve?",
                    "expected_concepts": [f"Basic purpose of {topic}", "High-level intuition", "Core motivation"],
                    "follow_ups": [f"Can you think of a common scenario where {topic} is applied?"]
                },
                {
                    "question_text": f"Let's step back to the basics of {topic}. What is one practical situation where an engineer would choose to use it?",
                    "expected_concepts": ["Real-world use case", "Basic mechanism", "Practical intuition"],
                    "follow_ups": ["What problem would occur if we didn't use it?"]
                }
            ]
            for cand in candidates:
                if not any(cand["question_text"].lower() == a.lower() for a in asked):
                    return cand
            return candidates[0]

        # 4. Vague / Missing Concepts Probe
        elif reason_category in ["vague_answer", "clarify_concept", "probe_missing"]:
            candidates = [
                {
                    "question_text": f"You mentioned {topic}. How does that mechanism work under the hood, and what trade-offs did you consider?",
                    "expected_concepts": [f"{topic} mechanics", "Implementation details", "Operational trade-offs"],
                    "follow_ups": ["How would you measure this in production?"]
                },
                {
                    "question_text": f"Regarding your point on {topic}, how would you implement this in code and what constraints would you monitor?",
                    "expected_concepts": ["Concrete implementation", "Resource constraints", "Metrics/Observability"],
                    "follow_ups": ["What failure modes could occur?"]
                }
            ]
            if "jwt" in ans_lower or "jwt" in topic.lower() or "auth" in ans_lower or "auth" in topic.lower():
                candidates.insert(0, {
                    "question_text": "You mentioned using JWT authentication. Where did you store the token on the client side, and how did you handle token expiration and refresh?",
                    "expected_concepts": ["Token storage", "Expiration & Refresh", "XSS/CSRF mitigation"],
                    "follow_ups": ["How do you revoke tokens?"]
                })
            elif "fastapi" in ans_lower or "fastapi" in topic.lower():
                candidates.insert(0, {
                    "question_text": "You mentioned FastAPI. What specific architectural features—such as ASGI or async endpoints—mattered in your project?",
                    "expected_concepts": ["FastAPI ASGI architecture", "Async concurrency", "Pydantic validation"],
                    "follow_ups": ["How do you handle blocking operations in FastAPI?"]
                })
            elif "hash" in ans_lower or "hash" in topic.lower():
                candidates.insert(0, {
                    "question_text": "How does the hash function distribute keys into buckets, and how do chaining or open addressing resolve collisions?",
                    "expected_concepts": ["Buckets & hash distribution", "Chaining vs Open Addressing", "Load factor"],
                    "follow_ups": ["What happens to performance when load factor exceeds 0.75?"]
                })
            elif "index" in ans_lower or "database" in ans_lower:
                candidates.insert(0, {
                    "question_text": "What data structure is typically used for relational database indexes on disk, and how does it balance search speed with update cost?",
                    "expected_concepts": ["B+ Tree structure", "Page splits", "Write overhead"],
                    "follow_ups": ["What are the implications of indexing high-cardinality columns?"]
                })

            for cand in candidates:
                if not any(cand["question_text"].lower() == a.lower() for a in asked):
                    return cand
            return candidates[0]

        # 5. Strong / Deep Dive Trade-offs Probe
        elif reason_category in ["strong_answer_tradeoffs", "drill_deep", "deepen"]:
            candidates = [
                {
                    "question_text": f"Under what specific scale or high-concurrency conditions would this approach to {topic} begin to bottleneck, and how would you mitigate that?",
                    "expected_concepts": ["Scale limits", "Concurrency bottlenecks", "Mitigation strategies"],
                    "follow_ups": ["How would you test this under simulated load?"]
                },
                {
                    "question_text": f"What are the primary operational failure modes and memory vs CPU trade-offs when scaling {topic} across multiple distributed nodes?",
                    "expected_concepts": ["Distributed failure modes", "Memory/CPU trade-offs", "Data consistency"],
                    "follow_ups": ["How do you ensure zero data loss during node failover?"]
                }
            ]
            if "jwt" in ans_lower:
                candidates.insert(0, {
                    "question_text": "Since JWTs are stateless, how do you handle immediate user session revocation, blacklisting, or permission changes across distributed microservices?",
                    "expected_concepts": ["Token revocation", "Redis blocklists", "Short-lived access tokens with refresh tokens"],
                    "follow_ups": ["What are the trade-offs of using an in-memory blocklist versus database lookups?"]
                })
            elif "hash" in ans_lower or "hash" in topic.lower() or "table" in ans_lower:
                candidates.insert(0, {
                    "question_text": "What happens to lookup performance when multiple keys collide, and what trade-off does that introduce in terms of worst-case complexity and memory?",
                    "expected_concepts": ["Collision resolution", "Worst-case O(N)", "Load factor"],
                    "follow_ups": ["How does dynamic resizing mitigate this?"]
                })
            elif "index" in ans_lower or "database" in ans_lower or "b-tree" in ans_lower:
                candidates.insert(0, {
                    "question_text": "How do B+ Tree page splits, write amplification, and WAL logging interact during high-frequency concurrent writes in a database?",
                    "expected_concepts": ["Page splits", "Write amplification", "WAL & Buffer pool interaction"],
                    "follow_ups": ["How would an LSM-Tree compare for write-heavy workloads?"]
                })

            for cand in candidates:
                if not any(cand["question_text"].lower() == a.lower() for a in asked):
                    return cand
            return candidates[0]

        # Default fallback probe
        return {
            "question_text": f"Could you elaborate on the practical considerations, failure modes, and trade-offs when implementing {topic} in production?",
            "expected_concepts": ["Production readiness", "Reliability", "Edge case handling"],
            "follow_ups": ["How would you monitor this in production?"]
        }

    @staticmethod
    async def generate_adaptive_follow_up(
        topic: str,
        question_text: str,
        candidate_answer: str,
        eval_feedback: str,
        reason_category: str,
        target_level: str = "entry",
        company_context: Optional[str] = None,
        previous_turns_context: Optional[List[Dict[str, str]]] = None,
        eval_dict: Optional[Dict[str, Any]] = None,
        asked_texts: Optional[List[str]] = None,
        memory: Optional[InterviewMemory] = None
    ) -> Dict[str, Any]:
        """
        Uses AI layer with prioritized Structured Interview Memory context to generate
        a sharp, natural, conversational follow-up question grounded in the candidate's previous response.
        """
        llm = AIFactory.get_llm_provider()

        # Build prioritized memory context
        memory_context = ""
        if memory:
            memory_context = MemoryManager.get_structured_llm_context(memory, max_recent_turns=3)
        elif previous_turns_context:
            recent = previous_turns_context[-2:]
            memory_context = "\n".join([f"- Q: {t.get('question', '')}\n  A: {t.get('answer', '')}" for t in recent])

        missing_c = ""
        misconceptions_c = ""
        demonstrated_c = ""
        if eval_dict:
            if eval_dict.get("demonstrated_concepts"):
                demonstrated_c = f"DEMONSTRATED CONCEPTS: {', '.join(eval_dict['demonstrated_concepts'])}"
            if eval_dict.get("missing_concepts"):
                missing_c = f"MISSING CONCEPTS: {', '.join(eval_dict['missing_concepts'])}"
            if eval_dict.get("misconceptions"):
                misconceptions_c = f"IDENTIFIED MISCONCEPTIONS: {', '.join(eval_dict['misconceptions'])}"

        prompt = f"""
You are an expert senior engineering interviewer conducting a realistic viva interview for a {target_level} software engineer.

STRUCTURED INTERVIEW MEMORY & CONVERSATION CONTEXT:
{memory_context or "Beginning of topic exploration."}

PREVIOUS QUESTION ASKED:
{question_text}

CANDIDATE ANSWER (UNTRUSTED):
<CANDIDATE_ANSWER>
{candidate_answer}
</CANDIDATE_ANSWER>

EVALUATION FEEDBACK:
{eval_feedback}
{demonstrated_c}
{missing_c}
{misconceptions_c}

FOLLOW-UP GOAL:
{reason_category}

COMPANY/ROLE CONTEXT:
{company_context or "Modern software engineering stack."}

PREVIOUSLY ASKED QUESTIONS (DO NOT REPEAT):
{asked_texts[-4:] if asked_texts else "None"}

INSTRUCTIONS:
1. Formulate a single concise, natural, spoken interviewer question that directly builds upon what the candidate said.
2. Use conversational transitions when referencing previous statements (e.g., "You mentioned...", "Earlier you said...", "Going back to the project you described...").
3. DO NOT use robotic phrasing like "Based on memory item #3" or "According to your previous score".
4. DO NOT use generic conversational filler like "Great answer!", "Excellent!", or "That's very interesting!".
5. If the candidate made a specific technical assertion (e.g. tools mentioned like Redis, FastAPI, PostgreSQL, JWT, Kafka), probe into implementation mechanics, trade-offs, or edge cases.
6. If the candidate was strong, test scalability, failure modes, and trade-offs.
7. If the candidate was vague or had a misconception, ask a targeted question to test if they can reason through it.
8. DO NOT invent facts that the candidate never said.

Return JSON:
{{
    "question_text": "Conversational follow-up question",
    "expected_concepts": ["concept 1", "concept 2"],
    "follow_ups": ["optional subsequent probe"]
}}
"""
        try:
            res = await llm.generate_json(
                prompt=prompt,
                system_prompt="You are a seasoned software engineering interviewer who remembers candidate answers and asks sharp, natural, conversational follow-up questions."
            )
            if isinstance(res, dict) and res.get("question_text"):
                return res
        except Exception:
            pass

        return FollowUpEngine.generate_deterministic_follow_up(
            topic=topic,
            reason_category=reason_category,
            candidate_answer=candidate_answer,
            target_level=target_level,
            eval_dict=eval_dict,
            asked_texts=asked_texts,
            memory=memory
        )
