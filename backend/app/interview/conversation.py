"""Phase 9: Conversational Follow-Up & Adaptive Probing Intelligence.

Decides when and how a human interviewer should probe an answer deeper,
distinguishing vague answers, strong answers, technical misconceptions, and resume claims.
"""

from typing import Dict, Any, Optional, List, Tuple
from app.ai.factory import AIFactory
from app.ai.prompt_builder import SafePromptBuilder


class FollowUpEngine:
    """Evaluates candidate answer depth and generates human-like follow-up probes."""

    @staticmethod
    def should_follow_up(
        last_eval_score: float,
        evidence: List[str],
        depth_score: float,
        turn_count_on_topic: int = 1,
        time_remaining_seconds: int = 600
    ) -> Tuple[bool, str]:
        """
        Determines whether to ask a follow-up question on the current topic or advance to a new topic.
        Returns (should_probe: bool, reason_category: str).
        """
        # If very little time remains (< 3 minutes), avoid opening a deep follow-up
        if time_remaining_seconds < 180:
            return False, "time_constrained"

        # Do not stay on the same topic for more than 2 consecutive follow-ups
        if turn_count_on_topic >= 3:
            return False, "topic_budget_exhausted"

        # Case 1: Vague / Low-depth answer on first attempt -> probe for specifics
        if depth_score < 6.0 and turn_count_on_topic == 1:
            return True, "vague_answer"

        # Case 2: High score / strong answer -> probe for architectural trade-offs or scale
        if last_eval_score >= 8.5 and turn_count_on_topic == 1:
            return True, "strong_answer_tradeoffs"

        # Case 3: Borderline partial understanding (5.0 <= score < 6.5) -> clarify core concept
        if 5.0 <= last_eval_score < 6.5 and turn_count_on_topic == 1:
            return True, "clarify_concept"

        return False, "advance_topic"

    @staticmethod
    def generate_deterministic_follow_up(
        topic: str,
        reason_category: str,
        candidate_answer: str,
        target_level: str = "entry"
    ) -> Dict[str, Any]:
        """
        Deterministic, rule-based fallback follow-up questions tailored to answer context.
        """
        ans_lower = (candidate_answer or "").lower()

        if reason_category == "vague_answer":
            if "database" in ans_lower or "sql" in ans_lower:
                text = f"You mentioned database optimization regarding {topic}. Could you walk me through the specific query or indexing change you made, and how you verified its impact?"
            elif "cache" in ans_lower or "redis" in ans_lower:
                text = "You noted caching in your answer. How did you handle cache invalidation and potential cache penetration or stampede scenarios?"
            else:
                text = f"Can you walk me through a concrete scenario or codebase example where you implemented {topic}, and what challenges arose?"
            return {
                "question_text": text,
                "expected_concepts": ["Concrete implementation details", "Bottleneck identification", "Verification/metrics"],
                "follow_ups": ["What trade-offs did that design introduce?"]
            }

        elif reason_category == "strong_answer_tradeoffs":
            if target_level in ["mid", "senior"]:
                text = f"That's a solid explanation of {topic}. Under what specific scale or concurrency conditions would this approach begin to degrade, and what alternative would you consider?"
            else:
                text = f"Good breakdown. What are the key performance and memory trade-offs of using this approach for {topic} compared to simpler alternatives?"
            return {
                "question_text": text,
                "expected_concepts": ["Scale limitations", "Memory vs CPU trade-offs", "Alternative architectures"],
                "follow_ups": ["How would you monitor this in production?"]
            }

        elif reason_category == "clarify_concept":
            text = f"Let's explore that a bit further. If the system experiences sudden unexpected failures during {topic}, how would you ensure data consistency and fault recovery?"
            return {
                "question_text": text,
                "expected_concepts": ["Fault tolerance", "Error recovery", "Consistency guarantees"],
                "follow_ups": ["How would you handle retry storms?"]
            }

        # Default fallback probe
        return {
            "question_text": f"Could you elaborate on the practical considerations when implementing {topic} in production?",
            "expected_concepts": ["Production readiness", "Reliability", "Edge case handling"],
            "follow_ups": []
        }

    @staticmethod
    async def generate_adaptive_follow_up(
        topic: str,
        question_text: str,
        candidate_answer: str,
        eval_feedback: str,
        reason_category: str,
        target_level: str = "entry",
        company_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uses Phase 8 AI layer to generate a natural, conversational follow-up question
        grounded in the candidate's previous response, with safe deterministic fallback.
        """
        llm = AIFactory.get_llm_provider()
        
        prompt = f"""
You are an expert technical interviewer conducting a human-like interview for a {target_level} engineer.

PREVIOUS QUESTION:
{question_text}

CANDIDATE ANSWER:
{candidate_answer}

EVALUATION FEEDBACK:
{eval_feedback}

FOLLOW-UP GOAL:
{reason_category}

COMPANY/ROLE CONTEXT:
{company_context or "General modern software engineering stack."}

INSTRUCTIONS:
1. Formulate a single concise, conversational follow-up question.
2. DO NOT use generic conversational filler like "Great answer" or "That's very interesting".
3. Probe specifically into the candidate's stated claims, architectural trade-offs, edge cases, or implementation details.
4. If the candidate was vague, ask for concrete examples. If they were strong, test scalability, failure modes, and trade-offs.

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
                system_prompt="You are a seasoned software engineering interviewer who asks sharp, conversational follow-up questions."
            )
            if isinstance(res, dict) and res.get("question_text"):
                return res
        except Exception:
            pass

        return FollowUpEngine.generate_deterministic_follow_up(
            topic=topic,
            reason_category=reason_category,
            candidate_answer=candidate_answer,
            target_level=target_level
        )
