"""Module 4B: Interviewer Persona Controller.

Enforces a concise, professional, authentic interviewer persona across all
LLM prompt turns. Eliminates filler preambles, maintains depth-calibrated tone,
and builds structured prompts for the interview engine.

Depth tone calibration:
  Depth 1–2: Encouraging, accessible language, foundational checks
  Depth 3:   Neutral, technical precision, implementation focus
  Depth 4–5: Peer-level architectural challenge, no hand-holding

Integration:
  Used by process_answer_turn_v2() in AdaptiveInterviewEngine as an optional
  prompt enrichment layer on top of the existing question generation logic.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.interview.depth_state_machine import QuestionDirective, TimeBudgetPhase

logger = logging.getLogger("ai_interviewer.persona_controller")

# Maximum tokens for a question turn to enforce conciseness
QUESTION_TURN_MAX_TOKENS = 200

# Professional interviewer persona base
BASE_PERSONA = """You are a senior technical interviewer. Your style:
- Concise: ONE clear question per response. Maximum 2 sentences total.
- No filler: Do NOT say \"Great!\", \"Excellent!\", \"That's interesting!\", or similar affirmations.
- No preamble: Start directly with the question — never with \"So,\" or lengthy context.
- Authentic: Sound like a real human interviewer, not a chatbot.
- Adaptive: If the candidate struggles, provide a brief 1-sentence hint then ask a simpler version.
- Professional: Maintain a respectful, focused tone throughout.

TRANSITION GROUNDING RULE (CRITICAL — never violate):
You must NEVER claim the candidate mentioned or explained a concept unless that exact term or
mechanism appears verbatim in their immediately previous response that is shown to you.
If the candidate gives a brief or generic answer (e.g. \"i have done a project on AI ML\",
\"no trade off\", \"ok\"), acknowledge ONLY what they actually said and immediately ask for
concrete specifics (e.g. \"Which specific model or algorithm did you implement in that project?\").
Do NOT say \"You mentioned {topic}\" or \"Regarding your point on {topic}\" when probing
a new concept the candidate has not referenced."""

# Probe-type to instruction mapping.
# GROUNDING NOTE: None of these templates use "You mentioned {topic}" or
# "Regarding your point on {topic}" phrasing — those presuppose candidate speech
# that may not have occurred.  Probes reference the topic directly as a technical subject.
PROBE_INSTRUCTIONS: Dict[str, str] = {
    "foundational_concept": (
        "Ask a clear conceptual question to verify the candidate understands the fundamentals of {topic}. "
        "Keep it approachable."
    ),
    "practical_implementation": (
        "Ask how the candidate would implement or has implemented {topic} in practice. "
        "Expect code-level or design-level reasoning."
    ),
    "architectural_design": (
        "Ask about architectural choices, trade-offs, or design patterns related to {topic}. "
        "Push for reasoning behind design decisions."
    ),
    "trade_offs_and_failure_modes": (
        "Challenge the candidate with a complex scenario involving {topic}: "
        "ask about failure modes, scaling bottlenecks, or edge cases. "
        "Expect expert-level reasoning."
    ),
    "expert_scale_and_optimization": (
        "Ask a research or optimization-level question about {topic}. "
        "Probe for knowledge of cutting-edge approaches, performance tuning, or novel architectures."
    ),
    "background_and_motivation": (
        "Ask the candidate a brief, warm background question to establish context. "
        "Focus on their experience with {topic} and what motivates their interest in this role."
    ),
    "system_design_or_behavioral": (
        "Ask a system design or behavioral question that connects their experience to {topic}. "
        "Use STAR format cues if behavioral."
    ),
    "wrap_up": (
        "Gracefully close the interview. Thank the candidate for their time and "
        "invite them to ask any questions they have about the role or company."
    ),
    "probe_candidate_claim": (
        "Follow up on a specific claim or assertion the candidate made about {topic}. "
        "Ask them to elaborate on how they built, implemented, or measured it."
    ),
    "clarify_misconception": (
        "The candidate may have a misconception about {topic}. "
        "Ask a probing question that exposes the gap without being condescending. "
        "Hint: {follow_up_hint}"
    ),
    "i_dont_know_foundation": (
        "The candidate indicated uncertainty about {topic}. "
        "Ask a simpler, more foundational version of the question. "
        "Be encouraging."
    ),
    # Fix 1 — removed 'vague_answer' template that used 'Regarding your point on {topic}'
    # The LLM must now derive the question directly from the candidate answer in context.
    "vague_answer": (
        "The candidate gave a high-level or incomplete answer about {topic}. "
        "Ask for a specific concrete example, implementation detail, or measured outcome. "
        "Do NOT presuppose what they said — reference the topic directly."
    ),
}


class InterviewerPersonaController:
    """
    Builds LLM system prompts and question turn instructions that enforce
    a professional, depth-calibrated, concise interviewer persona.
    """

    @staticmethod
    def build_system_prompt(
        role_title: str,
        company_name: str,
        candidate_name: str,
        directive: QuestionDirective,
        interview_type: str = "technical",
    ) -> str:
        """
        Build the full system prompt for a question turn.
        Incorporates BASE_PERSONA + depth-calibrated tone + probe-type instruction.
        """
        depth = directive.depth

        # Depth-calibrated tone
        if depth <= 2:
            tone_note = (
                "Tone: Warm and encouraging. The candidate may be early-career. "
                "Frame questions accessibly without talking down to them."
            )
        elif depth == 3:
            tone_note = (
                "Tone: Neutral and technical. Expect reasoned answers about implementation. "
                "Push back gently if answers are vague."
            )
        else:
            tone_note = (
                "Tone: Peer-level and challenging. The candidate is expected to demonstrate "
                "deep expertise. No hand-holding — ask directly and critically."
            )

        # Phase-specific instruction
        phase = directive.time_phase
        if phase == TimeBudgetPhase.OPENING.value:
            phase_instruction = (
                "PHASE: Opening (0–15% of session). "
                "Focus on candidate background, experience overview, and motivation. "
                "Keep questions broad and conversational."
            )
        elif phase == TimeBudgetPhase.CORE.value:
            phase_instruction = (
                "PHASE: Core Technical (15–75% of session). "
                "This is the main evaluation window. "
                "Probe technical depth rigorously and adaptively."
            )
        elif phase == TimeBudgetPhase.DESIGN_BEHAVIORAL.value:
            phase_instruction = (
                "PHASE: Design & Behavioral (75–90% of session). "
                "Shift to system design or behavioral questions. "
                "Connect candidate experience to real-world impact."
            )
        else:
            phase_instruction = (
                "PHASE: Wrap-Up (final 10% of session). "
                "Close gracefully. Summarize briefly and invite candidate questions."
            )

        # Probe-type instruction
        probe_template = PROBE_INSTRUCTIONS.get(
            directive.probe_type,
            PROBE_INSTRUCTIONS["practical_implementation"]
        )
        probe_instruction = probe_template.format(
            topic=directive.topic,
            follow_up_hint=directive.follow_up_hint or "probe gently",
        )

        # Persona note from directive
        persona_note_section = ""
        if directive.persona_note:
            persona_note_section = f"\nINTERVIEWER NOTE: {directive.persona_note}"

        system_prompt = f"""{BASE_PERSONA}

CONTEXT:
- Company: {company_name}
- Role: {role_title}
- Candidate: {candidate_name}
- Current Topic: {directive.topic}
- Depth Level: {depth}/5 ({directive.depth_label})

{tone_note}

{phase_instruction}

CURRENT QUESTION DIRECTIVE:
{probe_instruction}
{persona_note_section}

HARD CONSTRAINTS:
- Maximum response length: 2 sentences for a question turn.
- Do NOT provide the answer or over-hint.
- Do NOT repeat a question already asked in this session.
- If the candidate asks a clarifying question, answer in 1 sentence then re-ask yours.
- GROUNDING: Never say \"You mentioned {directive.topic}\" or \"Regarding your point on {directive.topic}\"
  unless the candidate's last answer (shown in the turn prompt) explicitly references that term.
  When transitioning to {directive.topic}, ask directly: \"Let's talk about {directive.topic}. [question]\""""

        return system_prompt

    @staticmethod
    def build_turn_prompt(
        directive: QuestionDirective,
        memory_summary: str,
        last_answer_text: Optional[str],
        asked_questions: List[str],
    ) -> str:
        """
        Build the user-role prompt content for the LLM question-generation turn.
        Provides conversation context and anti-repetition context.
        """
        parts: List[str] = []

        if memory_summary:
            parts.append(f"SESSION MEMORY SUMMARY:\n{memory_summary[:600]}")

        if last_answer_text:
            truncated = last_answer_text[:400]
            parts.append(f"\nCANDIDATE'S LAST ANSWER:\n\"{truncated}\"")

        if asked_questions:
            questions_list = "\n".join(f"  - {q[:100]}" for q in asked_questions[-5:])
            parts.append(f"\nQUESTIONS ALREADY ASKED (do not repeat):\n{questions_list}")

        parts.append(
            f"\nNow ask your next question about [{directive.topic}] "
            f"at depth level {directive.depth}/5 ({directive.depth_label}). "
            f"One question only. Maximum 2 sentences. "
            f"GROUNDING: Do NOT use 'You mentioned {directive.topic}' or "
            f"'Regarding your point on {directive.topic}' unless the candidate's "
            f"last answer shown above explicitly uses that exact term."
        )

        return "\n".join(parts)

    @staticmethod
    def get_question_generation_config() -> Dict[str, Any]:
        """
        Returns LLM generation config optimized for concise question generation.
        """
        return {
            "temperature": 0.4,
            "max_tokens": QUESTION_TURN_MAX_TOKENS,
        }

    @staticmethod
    def format_wrapup_message(
        role_title: str,
        company_name: str,
        topics_covered: List[str],
        average_depth: float,
    ) -> str:
        """
        Generate a natural wrap-up message for the end of the interview.
        """
        topic_summary = ", ".join(topics_covered[:4]) if topics_covered else "various technical areas"
        return (
            f"That covers everything I wanted to explore today. "
            f"We discussed {topic_summary}, and I have a good sense of your approach. "
            f"Do you have any questions about the {role_title} role at {company_name} "
            f"or what the next steps in our process look like?"
        )
