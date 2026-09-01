"""Phase 8/9: Hardened Mock & Offline AI Providers.

Provides deterministic, offline-capable implementations of LLM, Embedding, STT, and TTS
for development, local testing, and air-gapped environments without external API calls.
"""

import json
import hashlib
import time
import re
from typing import List, Dict, Any, Optional
from app.ai.base import LLMProvider, EmbeddingProvider, STTProvider, TTSProvider
from app.ai.schemas import validate_structured_data
from app.evaluation.validation import (
    classify_response_quality_state,
    is_empty_response,
    is_explicit_unknown,
    is_gibberish_or_nonlanguage,
    is_off_topic_response
)


class MockLLMProvider(LLMProvider):
    """Deterministic offline mock LLM provider with realistic, calibrated mock evaluation."""

    def __init__(self, model_name: str = "mock-llm-v1"):
        self.model_name = model_name
        self.provider_name = "mock"
        self.last_provider_used = "mock"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        prompt_lower = prompt.lower()
        if "evaluate" in prompt_lower or "score" in prompt_lower:
            return "The candidate provided a structured answer demonstrating relevant fundamentals."
        elif "question" in prompt_lower:
            return "Could you explain how indexing improves query performance in relational databases?"
        elif "summary" in prompt_lower or "report" in prompt_lower:
            return "Candidate demonstrates clear foundational technical knowledge with areas identified for deeper practice."
        elif "research" in prompt_lower or "company" in prompt_lower:
            return "Company focuses on high-scale distributed backend systems with strong engineering culture."
        return "Standard mock LLM response for demonstration."

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        data: Dict[str, Any] = {}

        # 1. Report generation mock fallback
        if "assessment report" in prompt_lower or "topic breakdown scores:" in prompt_lower or "executive candidate" in prompt_lower or "interview overall score:" in prompt_lower:
            score_match = re.search(r"overall score:\s*([0-9.]+)", prompt_lower)
            score_val = float(score_match.group(1)) if score_match else 50.0

            if score_val < 40.0:
                data = {
                    "strengths": ["Insufficient evidence to identify demonstrated strengths."],
                    "weaknesses": [
                        "Limited demonstrated understanding of foundational concepts.",
                        "Responses were too brief to establish technical knowledge or reasoning."
                    ],
                    "difficult_topics": ["Foundational Computer Science Concepts"],
                    "recommendations": [
                        "Review core CS fundamentals and practical implementations.",
                        "Practice explaining technical concepts and personal projects thoroughly in your own words."
                    ],
                    "executive_summary": f"The interview concluded with an overall score of {score_val}/100. The candidate provided brief or non-responsive answers and was unable to demonstrate sufficient foundational knowledge across the assessed competencies."
                }
            else:
                data = {
                    "strengths": [
                        "Demonstrates clear foundational technical understanding",
                        "Structured communication and reasoning style"
                    ],
                    "weaknesses": [
                        "Could deepen knowledge of edge-case failure modes and scale trade-offs",
                        "Deep architectural mechanics need further exploration"
                    ],
                    "difficult_topics": ["Distributed Systems", "Write Overhead Trade-offs"],
                    "recommendations": [
                        "Practice explaining underlying data structures and complexity trade-offs",
                        "Review production failure scenarios and disaster recovery strategies"
                    ],
                    "executive_summary": f"The candidate achieved an overall score of {score_val}/100 across assessed competencies. With targeted practice on architectural trade-offs, they will be well-prepared for placement rounds."
                }

        # 2. Answer Evaluation Mock
        elif (
            "<candidate_response_untrusted>" in prompt_lower
            or "candidate_answer" in prompt_lower
            or "candidate answer" in prompt_lower
            or "score calibration" in prompt_lower
            or "rubric" in prompt_lower
            or ("evaluat" in prompt_lower and ("correctness_score" in prompt_lower or "depth_score" in prompt_lower))
        ):
            cand_snippet = ""
            if "<candidate_response_untrusted>" in prompt_lower:
                parts = prompt_lower.split("<candidate_response_untrusted>", 1)[1]
                cand_snippet = parts.split("</candidate_response_untrusted>", 1)[0].strip()
            elif "<candidate_answer>" in prompt_lower:
                parts = prompt_lower.split("<candidate_answer>", 1)[1]
                cand_snippet = parts.split("</candidate_answer>", 1)[0].strip()
            elif "candidate answer:" in prompt_lower:
                parts = prompt_lower.split("candidate answer:", 1)[1]
                cand_snippet = parts.split("rubric", 1)[0].split("return", 1)[0].strip()
            elif "answer:" in prompt_lower:
                parts = prompt_lower.split("answer:", 1)[1]
                cand_snippet = parts.split("rubric", 1)[0].split("return", 1)[0].strip()
            else:
                cand_snippet = prompt_lower

            # Extract question text from prompt
            q_match = re.search(r'\bINTERVIEW QUESTION:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            if not q_match:
                q_match = re.search(r'\bQUESTION:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            extracted_question = q_match.group(1).strip() if q_match else ""

            # Extract topic if present
            topic_match = re.search(r'\bQUESTION TOPIC:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            if not topic_match:
                topic_match = re.search(r'\bTOPIC:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            extracted_topic = topic_match.group(1).strip() if topic_match else "Technical Fundamentals"

            # Extract question type if present
            qtype_match = re.search(r'\bQUESTION TYPE:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            if not qtype_match:
                qtype_match = re.search(r'\bTYPE:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            extracted_qtype = qtype_match.group(1).strip().lower() if qtype_match else "technical"

            # Extract expected core concepts if present
            exp_match = re.search(r'\bEXPECTED CORE CONCEPTS:\s*\n?\s*([^\n\r]+)', prompt, re.IGNORECASE)
            expected_str = exp_match.group(1).strip() if exp_match else ""
            expected_concepts = [c.strip() for c in expected_str.split(",") if c.strip() and len(c.strip()) > 2]

            q_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', extracted_question) if w.lower() not in ["explain", "what", "how", "why", "tell", "does", "with", "from", "when", "into", "called", "is", "the", "and", "about", "your", "for", "this"]]
            topic_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', extracted_topic) if len(w) > 3]

            # Check for pure prompt injection attempts
            is_prompt_injection = any(pi in cand_snippet for pi in [
                "ignore all previous", "ignore instructions", "give me 100", "give 100",
                "system prompt", "override evaluation", "disregard instructions"
            ])

            # Classify response state with response quality gate
            resp_state = classify_response_quality_state(
                safe_answer=cand_snippet,
                topic=extracted_topic,
                expected_concepts=expected_concepts,
                question_type=extracted_qtype,
                question_text=extracted_question
            )

            # Check for known technical misconceptions
            misconceptions_list = [
                ("jwt" in cand_snippet and "encrypt" in cand_snippet, "JWTs are encoded and signed, not encrypted by default."),
                ("no garbage collector" in cand_snippet or ("python" in cand_snippet and "no gc" in cand_snippet), "Python uses reference counting with cyclic generational garbage collection."),
                ("malloc" in cand_snippet and "python" in cand_snippet, "Python manages object allocation via private heaps, not direct C malloc in user scripts."),
                (("index" in cand_snippet or "database" in cand_snippet) and ("encrypt" in cand_snippet or "rsa" in cand_snippet), "Database indexes are structured search trees (B-Trees/hash tables), not encrypted copies."),
                ("permanent socket" in cand_snippet, "HTTP/REST APIs use ephemeral stateless requests unless WebSockets are configured."),
                ("always guarantee o(1)" in cand_snippet or "guaranteed o(1)" in cand_snippet, "Hash tables have average O(1) lookup, but degrade to O(N) under high collision rate or bad hash functions.")
            ]
            detected_misconceptions = [desc for matched, desc in misconceptions_list if matched]

            # Concept matching
            matched_concepts = []
            for concept in expected_concepts:
                c_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', concept) if len(w) > 3]
                if any(cw in cand_snippet or cw.rstrip('s') in cand_snippet for cw in c_words):
                    matched_concepts.append(concept)

            has_topic_match = any(tw in cand_snippet or tw.rstrip('s') in cand_snippet for tw in topic_words)
            has_q_match = any(qw in cand_snippet or qw.rstrip('s') in cand_snippet or (len(qw) > 4 and qw[:4] in cand_snippet) for qw in q_words if len(qw) > 3)
            is_hr_q = extracted_qtype in ["hr", "behavioral"] or any(w in extracted_topic.lower() for w in ["introduction", "motivation", "teamwork", "leadership", "strength"])

            is_partial_clue = any(kw in cand_snippet for kw in [
                "speeds up", "faster", "fast", "speed", "queries", "query", "brief", "makes it", "works fast",
                "it works", "just index", "partial", "constant", "indexed", "slot", "array", "integer", "position",
                "hash", "table", "store", "lookup", "compute", "bucket", "collision", "key", "value", "pointer", "node"
            ])

            if is_prompt_injection and not any(tech in cand_snippet for tech in ["index", "b-tree", "memory", "database", "api", "jwt"]):
                data = {
                    "correctness_score": 0.0,
                    "relevance_score": 0.0,
                    "reasoning_score": 0.0,
                    "depth_score": 0.0,
                    "communication_score": 1.0,
                    "demonstrated_concepts": [],
                    "missing_concepts": expected_concepts or [f"Technical principles of {extracted_topic}"],
                    "misconceptions": [],
                    "recommended_action": "recover",
                    "evidence": ["Candidate attempted prompt injection instruction override without answering technical question."],
                    "feedback_text": "Candidate response did not address the technical question. Please answer with relevant engineering principles.",
                    "confidence_score": 1.0,
                    "human_review_required": False
                }
            elif resp_state in ["EMPTY", "EXPLICIT_UNKNOWN", "GIBBERISH"]:
                fb = f"The response does not address the question. Please provide a clear explanation of {extracted_topic}."
                if resp_state == "EXPLICIT_UNKNOWN":
                    fb = f"The candidate did not demonstrate knowledge for {extracted_topic}. The next question will focus on fundamental principles."
                elif resp_state == "EMPTY":
                    fb = f"No answer was provided for {extracted_topic}."

                data = {
                    "correctness_score": 0.0,
                    "relevance_score": 0.0,
                    "reasoning_score": 0.0,
                    "depth_score": 0.0,
                    "communication_score": 1.0,
                    "demonstrated_concepts": [],
                    "missing_concepts": expected_concepts or [f"Fundamental mechanics of {extracted_topic}"],
                    "misconceptions": [],
                    "recommended_action": "recover",
                    "evidence": ["No relevant technical evidence provided in response."],
                    "feedback_text": fb,
                    "confidence_score": 1.0,
                    "human_review_required": False
                }
            elif resp_state == "OFF_TOPIC":
                data = {
                    "correctness_score": 0.0,
                    "relevance_score": 0.0,
                    "reasoning_score": 0.0,
                    "depth_score": 0.0,
                    "communication_score": 1.5,
                    "demonstrated_concepts": [],
                    "missing_concepts": expected_concepts or [f"Relevant technical concepts for {extracted_topic}"],
                    "misconceptions": [],
                    "recommended_action": "recover",
                    "evidence": ["Candidate provided an off-topic response unrelated to the question."],
                    "feedback_text": f"The response was off-topic and did not address {extracted_topic} or expected concepts.",
                    "confidence_score": 1.0,
                    "human_review_required": False
                }
            elif detected_misconceptions:
                data = {
                    "correctness_score": 1.5,
                    "relevance_score": 3.0,
                    "reasoning_score": 1.5,
                    "depth_score": 1.0,
                    "communication_score": 3.5,
                    "demonstrated_concepts": matched_concepts,
                    "missing_concepts": [c for c in expected_concepts if c not in matched_concepts] or ["Accurate architectural mechanics"],
                    "misconceptions": detected_misconceptions,
                    "recommended_action": "clarify",
                    "evidence": ["Candidate stated technical misconception in response."],
                    "feedback_text": f"Answer contains technical misconceptions ({detected_misconceptions[0]}). Review underlying mechanics.",
                    "confidence_score": 0.90,
                    "human_review_required": False
                }
            elif is_hr_q:
                # HR / Behavioral / Motivation answer evaluation
                hr_indicators = any(w in cand_snippet for w in [
                    "graduate", "student", "built", "project", "university", "experience", "learning",
                    "interested", "engineer", "software", "python", "react", "team", "work", "application",
                    "college", "degree", "passion", "career", "disagree", "disagreement", "review",
                    "trade-off", "tradeoff", "standard", "agreed", "communication", "collaborat",
                    "conflict", "resolv", "scheduled", "documented", "initiative", "lead"
                ])
                cand_len = len(cand_snippet.split())
                if hr_indicators and cand_len >= 5:
                    data = {
                        "correctness_score": 8.0,
                        "relevance_score": 8.5,
                        "reasoning_score": 8.0,
                        "depth_score": 7.0,
                        "communication_score": 8.0,
                        "demonstrated_concepts": ["Educational background", "Role motivation"],
                        "missing_concepts": [],
                        "misconceptions": [],
                        "recommended_action": "transition",
                        "evidence": [cand_snippet[:80]],
                        "feedback_text": "Clear personal background and role motivation provided.",
                        "confidence_score": 0.90,
                        "human_review_required": False
                    }
                elif hr_indicators:
                    data = {
                        "correctness_score": 6.0,
                        "relevance_score": 6.5,
                        "reasoning_score": 5.5,
                        "depth_score": 4.5,
                        "communication_score": 6.0,
                        "demonstrated_concepts": ["Brief background"],
                        "missing_concepts": ["Detailed project experience"],
                        "misconceptions": [],
                        "recommended_action": "follow_up",
                        "evidence": [cand_snippet[:80]],
                        "feedback_text": "Brief background provided. Provide more detail on specific projects.",
                        "confidence_score": 0.85,
                        "human_review_required": False
                    }
                else:
                    data = {
                        "correctness_score": 2.5,
                        "relevance_score": 3.0,
                        "reasoning_score": 2.0,
                        "depth_score": 1.5,
                        "communication_score": 3.0,
                        "demonstrated_concepts": [],
                        "missing_concepts": ["Background summary", "Role motivation"],
                        "misconceptions": [],
                        "recommended_action": "recover",
                        "evidence": [cand_snippet[:80]],
                        "feedback_text": "Response lacked concrete details about your background or motivation.",
                        "confidence_score": 0.80,
                        "human_review_required": False
                    }
            else:
                # Technical question evaluation grounded in expected concepts
                num_matched = len(matched_concepts)
                total_expected = max(1, len(expected_concepts))
                coverage = num_matched / float(total_expected)
                tech_depth_keywords = [
                    "b+ tree", "b+ trees", "b+tree", "b+trees", "btree", "btrees", "b-tree", "b-trees",
                    "disk i/o", "i/o", "o(log n)", "o(n)", "o(1)", "logarithmic", "constant time",
                    "constant-time", "write amplification", "page split", "page splits", "wal", "buffer pool",
                    "throughput", "latency", "overhead", "trade-off", "tradeoff", "trading off", "write cost",
                    "collision", "collisions", "chaining", "open addressing", "load factor",
                    "concurrency", "race condition", "deadlock", "organize data", "reduces disk", "reduce disk"
                ]
                has_tradeoffs = any(w in cand_snippet for w in tech_depth_keywords)
                is_solid_short = any(phrase in cand_snippet for phrase in ["constant-time", "constant time", "indexed access", "contiguous", "speed up", "faster queries", "frequent insertion", "integer position", "slot array"])

                if (coverage >= 0.6 and has_tradeoffs) or (len(cand_snippet.split()) >= 15 and has_tradeoffs) or (len(cand_snippet.split()) >= 30 and has_tradeoffs and (has_topic_match or num_matched >= 1)):
                    # Expert answer
                    data = {
                        "correctness_score": 9.2,
                        "relevance_score": 9.5,
                        "reasoning_score": 9.0,
                        "depth_score": 9.0,
                        "communication_score": 9.0,
                        "demonstrated_concepts": matched_concepts or [extracted_topic, "Trade-off Analysis"],
                        "missing_concepts": [],
                        "misconceptions": [],
                        "recommended_action": "deepen",
                        "evidence": [cand_snippet[:100]],
                        "feedback_text": f"Thorough explanation of {extracted_topic} covering core mechanics and operational trade-offs.",
                        "confidence_score": 0.95,
                        "human_review_required": False
                    }
                elif coverage >= 0.4 or (has_topic_match and len(cand_snippet.split()) >= 15) or has_tradeoffs or is_solid_short:
                    # Strong answer
                    data = {
                        "correctness_score": 8.5,
                        "relevance_score": 8.5,
                        "reasoning_score": 8.0,
                        "depth_score": 7.5 if len(cand_snippet.split()) >= 15 else 6.0,
                        "communication_score": 8.0,
                        "demonstrated_concepts": matched_concepts or [extracted_topic],
                        "missing_concepts": [c for c in expected_concepts if c not in matched_concepts][:2],
                        "misconceptions": [],
                        "recommended_action": "deepen" if len(cand_snippet.split()) >= 15 else "follow_up",
                        "evidence": [cand_snippet[:100]],
                        "feedback_text": f"Accurately addressed core principles of {extracted_topic}.",
                        "confidence_score": 0.90,
                        "human_review_required": False
                    }
                elif num_matched >= 1 or has_topic_match or has_q_match or is_partial_clue:
                    # Partial answer
                    missing = [c for c in expected_concepts if c not in matched_concepts] or ["Implementation trade-offs and complexity"]
                    data = {
                        "correctness_score": 5.5,
                        "relevance_score": 6.0,
                        "reasoning_score": 5.0,
                        "depth_score": 4.0,
                        "communication_score": 6.0,
                        "demonstrated_concepts": matched_concepts or [f"High-level notion of {extracted_topic}"],
                        "missing_concepts": missing[:2],
                        "misconceptions": [],
                        "recommended_action": "follow_up",
                        "evidence": [cand_snippet[:100]],
                        "feedback_text": f"Partially identified {extracted_topic} concepts, but omitted {', '.join(missing[:2])}.",
                        "confidence_score": 0.85,
                        "human_review_required": False
                    }
                else:
                    # Weak answer
                    missing = expected_concepts or [f"Core mechanics of {extracted_topic}"]
                    data = {
                        "correctness_score": 2.5,
                        "relevance_score": 3.0,
                        "reasoning_score": 2.0,
                        "depth_score": 1.5,
                        "communication_score": 3.0,
                        "demonstrated_concepts": [],
                        "missing_concepts": missing,
                        "misconceptions": [],
                        "recommended_action": "recover",
                        "evidence": [cand_snippet[:100]],
                        "feedback_text": f"High-level response lacking technical substance on {extracted_topic}.",
                        "confidence_score": 0.80,
                        "human_review_required": False
                    }

        # 3. Warm-up and Stage 1 question generation mock
        elif "warm-up" in prompt_lower or "warmup" in prompt_lower or "stage 1" in prompt_lower:
            comp_name = "our team"
            if "google" in prompt_lower:
                comp_name = "Google"
            elif "amazon" in prompt_lower:
                comp_name = "Amazon"
            elif "microsoft" in prompt_lower:
                comp_name = "Microsoft"
            
            role_name = "Software Engineer"
            if "backend" in prompt_lower:
                role_name = "Backend Engineer"
            elif "sde" in prompt_lower:
                role_name = "SDE-1"
            elif "frontend" in prompt_lower:
                role_name = "Frontend Engineer"
            elif "machine learning" in prompt_lower or "ml" in prompt_lower:
                role_name = "Machine Learning Engineer"

            greeting = "Hi, welcome"
            data = {
                "question_text": f"{greeting} to the interview for the {role_name} role at {comp_name}! To start off, could you introduce yourself, summarize your background, and share what drew you to apply to {comp_name}?",
                "expected_concepts": ["Clear self-introduction", "Background summary", f"Interest in {comp_name}"],
                "follow_ups": [f"What specific aspect of {comp_name}'s engineering challenges excites you most?"]
            }

        # 4. Conversational Follow-Up & Project Interrogation generation mock fallback
        elif (
            "follow-up goal:" in prompt_lower
            or "conversational follow-up" in prompt_lower
            or "follow-up probe" in prompt_lower
            or "interrogation directive:" in prompt_lower
            or "project interrogation" in prompt_lower
            or "follow_up" in prompt_lower
        ):
            is_hr = any(w in prompt_lower for w in ["introduction", "motivation", "background", "behavioral", "leadership", "teamwork", "strength"])
            
            if is_hr:
                if "recover" in prompt_lower or "unknown" in prompt_lower or "i_dont_know" in prompt_lower or "gibberish" in prompt_lower:
                    q_text = "What interests you about this role, and can you walk me through one project that is relevant to the work you'd be doing here?"
                elif "react" in prompt_lower or "python" in prompt_lower or "fastapi" in prompt_lower:
                    q_text = "You mentioned your project work. What specific part did you personally implement, and what was the most challenging technical decision you made?"
                else:
                    q_text = "Could you walk me through a key software project you've built recently and explain your individual role in it?"
            elif "level 2" in prompt_lower or "ownership" in prompt_lower:
                q_text = "In this project, what specific components and backend services did you personally design and implement versus the rest of the team?"
            elif "level 5" in prompt_lower or "design decisions" in prompt_lower:
                q_text = "Why did you choose FastAPI and PostgreSQL over alternative stacks for this service, and what trade-offs did you consider?"
            elif "level 6" in prompt_lower or "trade_offs" in prompt_lower or "tradeoff" in prompt_lower:
                q_text = "When implementing caching with Redis, what trade-offs did you make between data freshness and read latency?"
            elif "level 7" in prompt_lower or "security" in prompt_lower:
                q_text = "How did you secure your endpoints and validate untrusted user inputs to prevent injection and authentication bypass?"
            elif "level 9" in prompt_lower or "scalability" in prompt_lower:
                q_text = "Suppose your database traffic grew from 100 concurrent users to 10,000 concurrent users. Where would your system bottleneck first, and how would you scale it?"
            elif "level 10" in prompt_lower or "failure_modes" in prompt_lower or "failure" in prompt_lower:
                q_text = "What would happen to your system if Redis or a critical downstream service went down or experienced network partition?"
            elif "level 11" in prompt_lower or "production" in prompt_lower:
                q_text = "How did you instrument your system for observability, metrics collection, and production error alerting?"
            else:
                topic_str = "the underlying mechanics"
                if "redis" in prompt_lower and ("cache" in prompt_lower or "caching" in prompt_lower or "claim" in prompt_lower):
                    q_text = "You mentioned using Redis for caching to reduce repeated database queries. What specific data did you choose to cache, and how did you handle cache invalidation and cache stampede scenarios?"
                elif "fastapi" in prompt_lower and ("postgres" in prompt_lower or "postgresql" in prompt_lower or "database" in prompt_lower):
                    q_text = "You mentioned using FastAPI with PostgreSQL for storing interview sessions. How did you design the database relationships, and how did you handle asynchronous database sessions with SQLAlchemy?"
                elif "hash" in prompt_lower or "table" in prompt_lower or "lookup" in prompt_lower:
                    topic_str = "hash table lookup complexity and collision resolution"
                    if "strong" in prompt_lower or "tradeoff" in prompt_lower:
                        q_text = "What happens to lookup performance when many keys collide, and what trade-off does that introduce in worst-case time and memory?"
                    else:
                        q_text = f"Could you elaborate on the practical considerations and trade-offs when implementing {topic_str} in production?"
                elif "fastapi" in prompt_lower:
                    topic_str = "FastAPI asynchronous request handling"
                    q_text = "You mentioned working with FastAPI. Can you walk me through how you handled asynchronous request processing and concurrency in your endpoints?"
                elif "jwt" in prompt_lower:
                    topic_str = "JWT signature verification and token security"
                    q_text = "You mentioned using JWT authentication. Where did you store the token on the client side, and how did you handle token expiration and refresh token rotation?"
                elif "redis" in prompt_lower or "cache" in prompt_lower:
                    topic_str = "cache invalidation and stampede prevention"
                    q_text = "You mentioned using Redis for caching. How did you handle cache invalidation, TTL expiration, and stampede prevention?"
                elif "index" in prompt_lower or "database" in prompt_lower:
                    topic_str = "database index storage mechanics and write overhead"
                    q_text = "How do database indexes improve query execution speed, and what are the trade-offs on write operations?"
                elif "recover" in prompt_lower or "i_dont_know" in prompt_lower or "vague" in prompt_lower:
                    q_text = f"Let's step back to the fundamentals of {topic_str}. What is the core problem it solves, and why would an engineer choose it?"
                elif "strong" in prompt_lower or "tradeoff" in prompt_lower or "deepen" in prompt_lower or "drill_deep" in prompt_lower:
                    q_text = f"Under high concurrency or scale, what failure modes or bottlenecks might emerge with {topic_str}, and what trade-offs did you consider?"
                elif "clarif" in prompt_lower or "misconception" in prompt_lower:
                    q_text = f"Let's clarify that mechanism. How does the architecture verify state and maintain data integrity during {topic_str}?"
                else:
                    q_text = f"Could you elaborate on the practical considerations and trade-offs when implementing {topic_str} in production?"

            data = {
                "question_text": q_text,
                "expected_concepts": ["Implementation details", "Architectural trade-offs", "Edge case handling"],
                "follow_ups": ["How would you monitor and troubleshoot this in production?"]
            }

        # 5. Company & Role differentiated question generation mock fallback
        elif (
            "company & interview style:" in prompt_lower
            or "role & competency target:" in prompt_lower
            or "question" in prompt_lower
            or "generate the next natural interview question" in prompt_lower
        ):
            if "google" in prompt_lower:
                if "frontend" in prompt_lower or "react" in prompt_lower:
                    q_text = "When rendering large dynamic lists in React, how do you optimize virtual DOM diffing and prevent UI thread blocking for 10,000+ items?"
                    concepts = ["Virtualization / Windowing", "Re-render optimization", "Time complexity of DOM reconciliation"]
                elif "ml" in prompt_lower or "machine learning" in prompt_lower:
                    q_text = "Suppose your training loss decreases while validation loss plateaus and then starts increasing. How would you diagnose and systematically mitigate overfitting?"
                    concepts = ["Overfitting diagnosis", "Regularization", "Early stopping"]
                elif "senior" in prompt_lower or "lead" in prompt_lower:
                    q_text = "Walk me through how you would design a globally distributed, low-latency rate limiter handling millions of requests per second with strong consistency."
                    concepts = ["Distributed token bucket", "Consensus & synchronization", "Network latency"]
                else:
                    q_text = "Suppose we need to process a stream of incoming events. What data structure would you choose for efficient lookups and insertions, and what is its amortized time and space complexity?"
                    concepts = ["Data structure selection", "Amortized time complexity", "Memory space efficiency"]
            elif "amazon" in prompt_lower:
                q_text = "Looking at your backend architecture, what would happen if the database became temporarily unreachable during peak customer traffic, and how did you design for failure resilience?"
                concepts = ["Failure modes", "Circuit breaking / Retry with jitter", "Customer impact minimization"]
            elif "microsoft" in prompt_lower:
                q_text = "In your service architecture, how did you structure your service boundaries and dependency injection to ensure maintainability and testability?"
                concepts = ["Dependency injection", "Service separation", "Unit & integration testing"]
            elif "oracle" in prompt_lower:
                q_text = "How do B-Tree indexes differ from LSM trees in terms of read versus write amplification, and how do database transactions enforce serializable isolation?"
                concepts = ["B-Tree vs LSM Tree", "Read/Write amplification", "Transaction isolation levels & lock contention"]
            elif any(c in prompt_lower for c in ["accenture", "infosys", "tcs", "deloitte"]):
                q_text = "Can you walk me through how you implemented this technology in your project, focusing on the specific problem you solved and your individual responsibilities?"
                concepts = ["Project implementation", "Individual contribution", "Practical problem solving"]
            else:
                q_text = "How do database indexes improve query execution speed, and what are the trade-offs on write operations?"
                concepts = ["B-Tree indexing", "Disk I/O reduction", "Write overhead / index maintenance"]

            data = {
                "question_text": q_text,
                "expected_concepts": concepts,
                "follow_ups": ["What trade-offs did your approach introduce?"]
            }

        # 6. Research synthesis mock fallback
        elif "research" in prompt_lower or "company" in prompt_lower:
            data = {
                "description": "Global technology company specializing in cloud computing, developer platforms, and distributed systems.",
                "required_skills": ["Python", "Go", "Distributed Systems", "PostgreSQL"],
                "key_topics": ["System Design", "Concurrency", "Database Optimization"],
                "interview_categories": ["System Design", "Coding Algorithms", "Behavioral Leadership"],
                "culture_keywords": ["Customer Obsession", "Ownership", "Technical Excellence"],
                "confidence_level": "high"
            }

        # 7. Resume parsing mock fallback
        elif "resume" in prompt_lower or "extract" in prompt_lower:
            from app.resume.parser import ResumeParser
            resume_text = prompt
            if "RESUME TEXT:" in prompt:
                parts = prompt.split("RESUME TEXT:", 1)[1]
                if "Return a valid JSON" in parts:
                    resume_text = parts.split("Return a valid JSON", 1)[0]
                elif "Return a JSON" in parts:
                    resume_text = parts.split("Return a JSON", 1)[0]
                elif "Return JSON" in parts:
                    resume_text = parts.split("Return JSON", 1)[0]
                else:
                    resume_text = parts
            data = ResumeParser.deterministic_rule_parse(resume_text)
        # 8. Executive assessment report mock fallback
        elif "assessment report" in prompt_lower or "interview assessment report" in prompt_lower or "interview overall score:" in prompt_lower:
            score_match = re.search(r"overall score:\s*([0-9.]+)", prompt_lower)
            score_val = float(score_match.group(1)) if score_match else 50.0

            if score_val < 40.0:
                data = {
                    "strengths": ["Insufficient evidence to identify demonstrated strengths."],
                    "weaknesses": [
                        "Limited demonstrated understanding of foundational concepts.",
                        "Responses were too brief to establish technical knowledge or reasoning."
                    ],
                    "difficult_topics": ["Foundational Computer Science Concepts"],
                    "recommendations": [
                        "Review core CS fundamentals and practical implementations.",
                        "Practice explaining technical concepts and personal projects thoroughly in your own words."
                    ],
                    "executive_summary": f"The candidate achieved an overall score of {score_val}/100. Responses were insufficient to establish technical competence across assessed topics."
                }
            else:
                data = {
                    "strengths": ["Demonstrated understanding of core software engineering fundamentals."],
                    "weaknesses": ["Need deeper exploration of architectural trade-offs under high load."],
                    "difficult_topics": ["System Design"],
                    "recommendations": ["Review advanced scaling patterns and distributed system failure modes."],
                    "executive_summary": f"The candidate achieved an overall score of {score_val}/100 with demonstrated competence in core topics."
                }

        else:
            data = {"result": "mock_json_response", "status": "success"}

        # Validate against schema if schema was supplied
        if schema is not None:
            return validate_structured_data(data, schema, provider="mock")
        return data


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline mock embedding provider."""

    def __init__(self, dimension: int = 128, model_name: str = "mock-embed-v1"):
        self.dimension = dimension
        self.model_name = model_name

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate deterministic normalized float vector for input text."""
        if text is None:
            text = ""
        hash_val = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        vec = [((hash_val >> (i % 32)) & 0xFF) / 255.0 for i in range(self.dimension)]
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            return [round(x / norm, 6) for x in vec]
        return vec

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Preserve exact batch ordering."""
        if not texts:
            return []
        return [await self.embed_text(t, model=model) for t in texts]


class MockSTTProvider(STTProvider):
    """Offline speech-to-text mock provider."""

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict[str, Any]:
        return {
            "transcript": "Database indexes use B-Trees to speed up data retrieval operations by reducing disk I/O.",
            "confidence": 0.98,
            "duration_sec": 4.5
        }


class MockTTSProvider(TTSProvider):
    """Offline text-to-speech mock provider generating valid audible PCM WAV audio."""

    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        # Generate a valid, audible 0.5s 440Hz sine wave PCM WAV audio byte sequence
        import math
        import struct
        sample_rate = 16000
        duration_s = 0.5
        num_samples = int(sample_rate * duration_s)
        frequency = 440.0  # Standard A4 tone
        
        pcm_data = bytearray()
        for i in range(num_samples):
            # Generate soft sine wave sample (16-bit signed integer)
            sample_val = int(12000.0 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            pcm_data.extend(struct.pack('<h', sample_val))
            
        data_size = len(pcm_data)
        header = bytearray(b'RIFF')
        header.extend(struct.pack('<I', 36 + data_size))
        header.extend(b'WAVEfmt ')
        header.extend(struct.pack('<I', 16))          # Subchunk1Size for PCM
        header.extend(struct.pack('<H', 1))           # AudioFormat 1 = PCM
        header.extend(struct.pack('<H', 1))           # NumChannels 1 = Mono
        header.extend(struct.pack('<I', sample_rate)) # SampleRate
        header.extend(struct.pack('<I', sample_rate * 2)) # ByteRate
        header.extend(struct.pack('<H', 2))           # BlockAlign
        header.extend(struct.pack('<H', 16))          # BitsPerSample
        header.extend(b'data')
        header.extend(struct.pack('<I', data_size))
        
        return bytes(header + pcm_data)
