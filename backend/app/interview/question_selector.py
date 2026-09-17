"""Phase 7/9: Question Selection, Grounded Generation & Semantic Repetition Prevention.

Selects, validates, and generates high-quality, company-, role-, and resume-tailored
interview questions with strict duplicate prevention, conversational transitions,
and Structured Interview Memory integration.
"""

import re
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Question, Company, Role
from app.rag.rag_engine import RAGEngine
from app.ai.factory import AIFactory
from app.interview.memory import InterviewMemory, MemoryManager
from app.companies.strategy_engine import CompanyStrategyEngine


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
    """
    Check if new_text is an exact or near-duplicate of any existing asked question.
    Distinguishes legitimate follow-ups from semantic duplicates.
    """
    norm_new = normalize_text_for_comparison(new_text)
    if not norm_new:
        return False
    set_new = set(norm_new.split())

    for ext in existing_texts:
        norm_ext = normalize_text_for_comparison(ext)
        if not norm_ext:
            continue
        # Exact match
        if norm_new == norm_ext:
            return True
        # Exact substring containment for long questions
        if len(norm_new) > 30 and norm_new in norm_ext:
            return True
        if len(norm_ext) > 30 and norm_ext in norm_new:
            return True
        set_ext = set(norm_ext.split())
        if set_new and set_ext:
            overlap = len(set_new.intersection(set_ext)) / float(max(len(set_new), len(set_ext)))
            if overlap >= 0.72:
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
    if q_type not in ["technical", "conceptual", "coding", "behavioral", "hr", "resume", "database", "system_design"]:
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
    """Selects from pre-existing bank or generates validated grounded questions with memory awareness."""

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
        resume_context: Optional[str] = None,
        previous_context: Optional[List[Dict[str, str]]] = None,
        eval_dict: Optional[Dict[str, Any]] = None,
        memory: Optional[InterviewMemory] = None,
        candidate_level: str = "entry",
        allow_llm_generation: bool = True
    ) -> Question:
        """
        Selects an existing matching question or generates a company/role/resume-tailored question.
        Priority:
        1. Dynamic AI generation grounded in RAG + Structured Memory + Resume Claims
        2. Matching unasked question bank item
        3. Predefined behavioral/HR fallback
        4. Safe deterministic fallback

        allow_llm_generation=False skips step 1. The caller passes it when this
        turn has already spent an LLM call on a question that was then rejected
        as a duplicate: generating again would be a second charge, a second
        wait, and a second chance at the same duplicate, when steps 2-4 can
        supply a question that is guaranteed not to repeat one already asked.
        """
        clean_type = (interview_type or "technical").lower()
        clean_diff = (difficulty or "medium").lower()
        clean_topic = topic or "Technical Fundamentals"

        # Fetch previously asked question texts for duplicate checking
        asked_texts: List[str] = []
        if memory and memory.asked_question_texts:
            asked_texts = list(memory.asked_question_texts)
        elif asked_question_ids:
            stmt_asked = select(Question.question_text).where(Question.id.in_(asked_question_ids))
            res_asked = await self.db.execute(stmt_asked)
            asked_texts = [row[0] for row in res_asked.all()]

        # Step 1: Dynamic generation grounded in RAG + Memory Context.
        # Skipped entirely when the caller has already spent this turn's LLM
        # call -- everything below step 1 is local, so the turn falls straight
        # through to the bank instead of making a second provider round trip.
        if not allow_llm_generation:
            return await self._select_without_generation(
                clean_type=clean_type,
                clean_topic=clean_topic,
                clean_diff=clean_diff,
                company_id=company_id,
                role_id=role_id,
                asked_question_ids=asked_question_ids,
                asked_texts=asked_texts,
            )

        rag_context = ""
        try:
            rag_context = await self.rag_engine.get_relevant_context(
                query=clean_topic,
                company_id=company_id,
                role_id=role_id
            )
        except Exception:
            rag_context = "General engineering practices."

        # Format structured memory context
        memory_summary = ""
        if memory:
            memory_summary = MemoryManager.get_structured_llm_context(memory, max_recent_turns=3)
        elif previous_context:
            memory_summary = "\n".join([f"- Asked: {p.get('question', '')}\n  Candidate Answer: {p.get('answer', '')}" for p in previous_context[-2:]])

        eval_summary = ""
        if eval_dict:
            missing = eval_dict.get("missing_concepts", [])
            misconceptions = eval_dict.get("misconceptions", [])
            if missing:
                eval_summary += f"\nPREVIOUSLY MISSING CONCEPTS: {', '.join(missing)}"
            if misconceptions:
                eval_summary += f"\nDETECTED MISCONCEPTIONS: {', '.join(misconceptions)}"

        # Compute Phase 9 Company & Role Strategy
        company_slug = None
        role_title = None
        if company_id:
            c_stmt = select(Company).where(Company.id == company_id)
            c_res = await self.db.execute(c_stmt)
            c_obj = c_res.scalars().first()
            if c_obj:
                company_slug = c_obj.slug or c_obj.name
        if role_id:
            r_stmt = select(Role).where(Role.id == role_id)
            r_res = await self.db.execute(r_stmt)
            r_obj = r_res.scalars().first()
            if r_obj:
                role_title = r_obj.title

        strategy = CompanyStrategyEngine.compute_interview_strategy(
            company_slug_or_name=company_slug,
            role_title=role_title,
            candidate_level=candidate_level or "entry",
            memory=memory,
            current_turn=len(asked_texts) + 1
        )
        company_profile = CompanyStrategyEngine.get_company_profile(company_slug)
        role_profile = CompanyStrategyEngine.get_role_profile(role_title)

        llm = AIFactory.get_llm_provider()
        prompt = f"""
You are an experienced technical interviewer at {company_profile.display_name} conducting a {clean_type} interview for a {candidate_level} {role_profile.display_name} position.

COMPANY & INTERVIEW STYLE:
- Company: {company_profile.display_name} ({company_profile.difficulty_profile})
- Question Style: {company_profile.question_style}
- Technical Depth: {company_profile.technical_depth}/10
- Problem Solving Emphasis: {company_profile.problem_solving_emphasis}/10
- Public Notes: {company_profile.public_pattern_notes}

ROLE & COMPETENCY TARGET:
- Role Family: {role_profile.display_name}
- Target Topic/Competency: {clean_topic}
- Role Architecture Focus: {role_profile.architecture_focus}
- Core Technologies: {', '.join(role_profile.key_technologies)}

CANDIDATE LEVEL & DESIRED DIFFICULTY:
- Seniority: {candidate_level} (Difficulty: {strategy.desired_difficulty:.1f}/10)

STRUCTURED INTERVIEW MEMORY & CONVERSATION HISTORY:
{memory_summary or "Starting new topic exploration."}
{eval_summary}

PREVIOUSLY ASKED QUESTIONS (DO NOT DUPLICATE OR REPEAT):
{asked_texts[-4:] if asked_texts else "None"}

INSTRUCTIONS:
1. Frame ONE clear, spoken question reflecting {company_profile.display_name}'s technical style and {role_profile.display_name}'s domain requirements.
2. Keep the question CONCISE, natural, and conversational when spoken aloud (1-2 sentences, under 40 words). Avoid huge paragraphs.
3. DO NOT use cold written-exam phrasing like "Question 3: Define..." or robotic questionnaire templates.
4. STRICT GROUNDING: Never tell the candidate "You implemented X" unless verified in resume or previously stated by candidate. Say "You mentioned X..." or "Your resume lists X...".
5. Focus on WHY, HOW, trade-offs, architecture, scalability, edge cases, and failure scenarios.
6. Keep the question grounded in the target topic ({clean_topic}).
7. If changing topic, connect naturally with projects or tools previously mentioned by the candidate when relevant.
8. DO NOT claim proprietary company questions or fabricate candidate experience.

Return JSON:
{{
    "question_text": "The conversational question text",
    "expected_concepts": ["concept 1", "concept 2"],
    "follow_ups": ["possible subsequent probe"]
}}
"""
        try:
            generated_json = await llm.generate_json(
                prompt,
                system_prompt=f"You are a seasoned human technical interviewer who remembers candidate experience and asks realistic, conversational viva questions for a {clean_type} interview."
            )
            validated_data = validate_question_data(
                generated_json,
                default_topic=clean_topic,
                default_diff=clean_diff,
                default_type="behavioral" if clean_type == "behavioral" else ("hr" if clean_type == "hr" else "technical")
            )

            # Ensure the generated question is not a duplicate of already asked questions
            is_dup = is_duplicate_question(validated_data["question_text"], asked_texts)
            if memory:
                is_dup = is_dup or MemoryManager.is_semantic_duplicate(validated_data["question_text"], memory)

            if not is_dup:
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
        except Exception:
            pass

        # Steps 2-4 are local: question bank, then HR/behavioural presets,
        # then a deterministic question. Shared with the no-generation path.
        return await self._select_without_generation(
            clean_type=clean_type,
            clean_topic=clean_topic,
            clean_diff=clean_diff,
            company_id=company_id,
            role_id=role_id,
            asked_question_ids=asked_question_ids,
            asked_texts=asked_texts,
        )

    async def _select_without_generation(
        self,
        clean_type: str,
        clean_topic: str,
        clean_diff: str,
        company_id: int,
        role_id: int,
        asked_question_ids: List[int],
        asked_texts: List[str],
    ) -> Question:
        """Pick a question without calling a provider.

        The question bank first, then the HR/behavioural presets, then a
        deterministic question on the topic. Every branch checks the asked
        list, so none of them can repeat a question already put to the
        candidate."""
        # Step 2: Query question bank for matching topic and type (only if not duplicate)
        stmt = select(Question)
        if clean_type in ["hr", "behavioral"]:
            stmt = stmt.where(Question.question_type == clean_type)
        elif clean_type == "technical":
            stmt = stmt.where(Question.question_type.in_(["technical", "coding", "conceptual", "database", "system_design"]))
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
                    return new_q

        # Step 4: Safe deterministic fallback question
        fallback_data = {
            "question_text": f"Let's discuss {clean_topic}. When designing and implementing solutions in this area, how do you optimize for system performance, reliability, and concurrency trade-offs?",
            "expected_concepts": [clean_topic, "Scalability", "Error Handling & Trade-offs"],
            "follow_ups": ["What architectural trade-offs did you consider in your design?"],
            "difficulty": clean_diff,
            "question_type": "technical",
            "topic": clean_topic
        }
        new_question = Question(
            company_id=company_id,
            role_id=role_id,
            topic=fallback_data["topic"],
            difficulty=fallback_data["difficulty"],
            question_type=fallback_data["question_type"],
            question_text=fallback_data["question_text"],
            expected_concepts=fallback_data["expected_concepts"],
            follow_ups=fallback_data["follow_ups"]
        )
        self.db.add(new_question)
        await self.db.commit()
        await self.db.refresh(new_question)
        return new_question
