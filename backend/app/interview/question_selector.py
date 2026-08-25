"""Phase 9: Question Selection, Grounded Generation & Duplicate Prevention.

Selects, validates, and generates high-quality, company- and role-tailored interview
questions with strict duplicate prevention and deterministic fallbacks.
"""

import re
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Question
from app.rag.rag_engine import RAGEngine
from app.ai.factory import AIFactory
from app.ai.prompt_builder import SafePromptBuilder


HR_FALLBACK_QUESTIONS = [
    {
        "topic": "Introduction & Motivation",
        "question_type": "hr",
        "question_text": "Tell me about yourself, your educational background, and why you are interested in this specific role and company.",
        "expected_concepts": ["Clear career trajectory", "Relevant technical interests", "Alignment with company mission"],
        "follow_ups": ["What inspired you to choose software engineering?"]
    },
    {
        "topic": "Strengths & Weaknesses",
        "question_type": "hr",
        "question_text": "What do you consider your greatest technical strength, and what is an area or skill you are actively working to improve?",
        "expected_concepts": ["Self-awareness", "Proactive learning mindset", "Constructive growth strategy"],
        "follow_ups": ["Can you give an example of how you overcame a recent learning curve?"]
    },
    {
        "topic": "Conflict Resolution & Teamwork",
        "question_type": "behavioral",
        "question_text": "Describe a situation where you had a technical disagreement with a teammate or team lead. How did you handle it and reach a resolution?",
        "expected_concepts": ["Active listening", "Data-driven argumentation", "Empathy & collaboration"],
        "follow_ups": ["What would you do differently if faced with the same scenario again?"]
    },
    {
        "topic": "Ownership & Leadership",
        "question_type": "behavioral",
        "question_text": "Tell me about a time you took initiative on a project outside of your normal responsibilities to solve a critical problem.",
        "expected_concepts": ["Bias for action", "Accountability", "Measurable outcome"],
        "follow_ups": ["What was the overall impact on the team or deliverables?"]
    }
]


def normalize_text_for_comparison(text: str) -> str:
    """Normalize question text to detect near-duplicates."""
    if not text:
        return ""
    clean = re.sub(r'[^\w\s]', '', text.lower())
    return " ".join(clean.split())


def is_duplicate_question(new_text: str, existing_texts: List[str]) -> bool:
    """Check if new_text is an exact or near-duplicate of any existing asked question."""
    norm_new = normalize_text_for_comparison(new_text)
    if not norm_new:
        return False
    set_new = set(norm_new.split())

    for ext in existing_texts:
        norm_ext = normalize_text_for_comparison(ext)
        if not norm_ext:
            continue
        if norm_new == norm_ext or (len(norm_new) > 20 and norm_new in norm_ext) or (len(norm_ext) > 20 and norm_ext in norm_new):
            return True
        set_ext = set(norm_ext.split())
        if set_new and set_ext:
            overlap = len(set_new.intersection(set_ext)) / float(max(len(set_new), len(set_ext)))
            if overlap >= 0.70:
                return True
    return False


def validate_question_data(data: Dict[str, Any], default_topic: str, default_diff: str, default_type: str) -> Dict[str, Any]:
    """Validate and sanitize raw question dictionary before persistence."""
    q_text = data.get("question_text", "").strip() if isinstance(data.get("question_text"), str) else ""
    if not q_text or len(q_text) < 10:
        q_text = f"Could you walk me through your engineering experience with {default_topic}?"

    concepts = data.get("expected_concepts")
    if not isinstance(concepts, list) or len(concepts) == 0:
        concepts = [default_topic, "Core Implementation Details", "Trade-offs"]

    follow_ups = data.get("follow_ups")
    if not isinstance(follow_ups, list):
        follow_ups = []

    diff = data.get("difficulty", default_diff)
    if diff not in ["easy", "medium", "hard"]:
        diff = default_diff

    q_type = data.get("question_type", default_type)
    if q_type not in ["technical", "conceptual", "coding", "behavioral", "hr", "resume"]:
        q_type = default_type

    return {
        "question_text": q_text,
        "expected_concepts": concepts,
        "follow_ups": follow_ups,
        "difficulty": diff,
        "question_type": q_type,
        "topic": data.get("topic") or default_topic
    }


class QuestionSelector:
    """Selects from pre-existing bank or generates validated grounded questions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_engine = RAGEngine(db)

    async def select_or_generate_question(
        self,
        company_id: int,
        role_id: int,
        topic: str,
        difficulty: str,
        asked_question_ids: List[int],
        interview_type: str = "technical",
        resume_context: Optional[str] = None
    ) -> Question:
        """
        Selects an existing matching question or generates a company/role/resume-tailored question.
        Priority:
        1. Matching question bank item
        2. Fallback unasked bank item
        3. Predefined behavioral/HR fallback
        4. Grounded RAG + Resume AI generation
        5. Safe deterministic fallback
        """
        clean_type = (interview_type or "technical").lower()
        clean_diff = (difficulty or "medium").lower()
        clean_topic = topic or "Technical Fundamentals"

        # Fetch previously asked question texts for duplicate checking
        asked_texts: List[str] = []
        if asked_question_ids:
            stmt_asked = select(Question.question_text).where(Question.id.in_(asked_question_ids))
            res_asked = await self.db.execute(stmt_asked)
            asked_texts = [row[0] for row in res_asked.all()]

        # Step 1: Query question bank for matching topic and type
        stmt = select(Question)
        if clean_type in ["hr", "behavioral"]:
            stmt = stmt.where(Question.question_type == clean_type)
        elif clean_type == "technical":
            stmt = stmt.where(Question.question_type.in_(["technical", "coding", "conceptual"]))
            if clean_topic:
                stmt = stmt.where(Question.topic == clean_topic)
        else:
            if clean_topic:
                stmt = stmt.where(Question.topic == clean_topic)

        if asked_question_ids:
            stmt = stmt.where(Question.id.not_in(asked_question_ids))

        result = await self.db.execute(stmt)
        matched_question = result.scalars().first()

        if matched_question and not is_duplicate_question(matched_question.question_text, asked_texts):
            return matched_question

        # Step 2: Query fallback question from bank for any unasked question
        stmt_fallback = select(Question).where(
            Question.id.not_in(asked_question_ids) if asked_question_ids else True
        )
        if clean_type in ["hr", "behavioral"]:
            stmt_fallback = stmt_fallback.where(Question.question_type.in_(["hr", "behavioral"]))

        res_fallback = await self.db.execute(stmt_fallback)
        fallback_q = res_fallback.scalars().first()

        if fallback_q and not is_duplicate_question(fallback_q.question_text, asked_texts):
            return fallback_q

        # Step 3: Check HR/Behavioral predefined fallbacks if relevant
        if clean_type in ["hr", "behavioral"]:
            for item in HR_FALLBACK_QUESTIONS:
                if not is_duplicate_question(item["question_text"], asked_texts):
                    new_q = Question(
                        company_id=company_id,
                        role_id=role_id,
                        topic=item["topic"],
                        difficulty="medium",
                        question_type=item["question_type"],
                        question_text=item["question_text"],
                        expected_concepts=item["expected_concepts"],
                        follow_ups=item["follow_ups"]
                    )
                    self.db.add(new_q)
                    await self.db.commit()
                    await self.db.refresh(new_q)
                    if new_q.id not in asked_question_ids:
                        return new_q

        # Step 4: Dynamic generation grounded in RAG + Resume Context
        rag_context = ""
        try:
            rag_context = await self.rag_engine.get_relevant_context(
                query=clean_topic,
                company_id=company_id,
                role_id=role_id
            )
        except Exception:
            rag_context = "General engineering practices."

        llm = AIFactory.get_llm_provider()
        prompt = f"""
Generate an interview question for topic '{clean_topic}' at difficulty level '{clean_diff}' for a '{clean_type}' interview.

TRUSTED COMPANY/ROLE KNOWLEDGE:
{rag_context}

CANDIDATE RESUME CONTEXT:
{resume_context or "Candidate with standard engineering background."}

PREVIOUSLY ASKED QUESTIONS (DO NOT DUPLICATE):
{asked_texts[-3:] if asked_texts else "None"}

INSTRUCTIONS:
1. Frame the question naturally as an experienced technical interviewer.
2. Ask WHY, HOW, trade-offs, scale, or failure scenarios. Avoid simple "Define X" textbook questions.
3. Keep the question focused on the requested topic.

Return JSON:
{{
    "question_text": "The conversational question text",
    "expected_concepts": ["concept 1", "concept 2"],
    "follow_ups": ["possible follow up question"]
}}
"""
        validated_data = None
        try:
            generated_json = await llm.generate_json(
                prompt,
                system_prompt=f"You are a human technical interviewer asking realistic questions for a {clean_type} interview."
            )
            validated_data = validate_question_data(
                generated_json,
                default_topic=clean_topic,
                default_diff=clean_diff,
                default_type="behavioral" if clean_type == "behavioral" else ("hr" if clean_type == "hr" else "technical")
            )
        except Exception:
            # Deterministic fallback question
            validated_data = {
                "question_text": f"How do you optimize system performance, latency, and reliability when designing solutions with {clean_topic}?",
                "expected_concepts": [clean_topic, "Scalability", "Error Handling"],
                "follow_ups": ["What trade-offs did you consider in your architectural choice?"],
                "difficulty": clean_diff,
                "question_type": "technical",
                "topic": clean_topic
            }

        new_question = Question(
            company_id=company_id,
            role_id=role_id,
            topic=validated_data["topic"],
            difficulty=validated_data["difficulty"],
            question_type=validated_data["question_type"],
            question_text=validated_data["question_text"],
            expected_concepts=validated_data["expected_concepts"],
            follow_ups=validated_data["follow_ups"]
        )
        self.db.add(new_question)
        await self.db.commit()
        await self.db.refresh(new_question)
        return new_question
