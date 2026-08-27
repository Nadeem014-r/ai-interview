import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.core.database import AsyncSessionLocal
from app.db.models import User, Company, Role, Interview, Question, Answer
from app.evaluation.evaluator import AnswerEvaluator
from app.interview.engine import AdaptiveInterviewEngine
from app.ai.factory import AIFactory

async def run_live_multi_turn_test():
    print("\n" + "="*80)
    print("CRITICAL LIVE MULTI-TURN API TEST RUN")
    print("="*80)
    
    async with AsyncSessionLocal() as session:
        ts = datetime.utcnow().timestamp()
        company = Company(name=f"LiveTestCorp_{ts}", slug=f"livetest_{ts}", description="Live Multi-Turn Validation")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        role = Role(
            company_id=company.id,
            title="Backend Engineer",
            level="entry",
            key_topics=["Data Structures", "System Design", "Database Indexing", "API Security"]
        )
        session.add(role)
        await session.commit()
        await session.refresh(role)

        user = User(
            email=f"livetest_{ts}@edu.com",
            hashed_password="hashed_pw",
            full_name="Live Test Candidate",
            role="candidate"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            interview_type="technical",
            duration_minutes=30,
            status="in_progress",
            start_time=datetime.utcnow()
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        # Create Q1 (Warm-up / Intro)
        q1 = Question(
            company_id=company.id,
            role_id=role.id,
            topic="Introduction & Motivation",
            difficulty="easy",
            question_type="hr",
            question_text="Tell me about your technical background and why you are interested in this role.",
            expected_concepts=["Educational background", "Role motivation"]
        )
        session.add(q1)
        await session.commit()
        await session.refresh(q1)

        engine = AdaptiveInterviewEngine(session)
        state = await engine.initialize_interview_state(
            interview,
            ["Introduction & Motivation", "Data Structures", "System Design", "Database Indexing", "API Security"],
            initial_question_id=q1.id
        )

        test_turns = [
            ("Turn 1 (Warmup)", "I am a fresh computer science graduate who built full-stack web applications using React and Python."),
            ("Turn 2 (I don't know)", "I don't know. I have never studied this concept."),
            ("Turn 3 (Irrelevant)", "Paris is the capital of France and the weather is very nice today."),
            ("Turn 4 (Strong Technical)", "Database indexing uses balanced B+ Trees to organize table records on disk. Instead of scanning every row with O(N) disk I/O, the search traverses tree levels in O(log N) operations. However, indexes introduce write overhead and storage trade-offs because inserts, updates, and deletes require updating the tree pages.")
        ]

        current_q = q1
        asked_ids = []

        llm = AIFactory.get_llm_provider()
        provider_name = getattr(llm, "last_provider_used", type(llm).__name__)

        for idx, (label, candidate_ans) in enumerate(test_turns, 1):
            print(f"\n--- {label} ---")
            print(f"Active Question ID: {current_q.id}")
            print(f"Active Question Topic: '{current_q.topic}'")
            print(f"Active Question Type: '{current_q.question_type}'")
            print(f"Active Question Text: '{current_q.question_text}'")
            print(f"Candidate Answer: '{candidate_ans}'")

            # Evaluate Answer
            eval_res = await AnswerEvaluator.evaluate_answer(
                question_text=current_q.question_text,
                expected_concepts=current_q.expected_concepts or [],
                candidate_answer=candidate_ans,
                topic=current_q.topic,
                question_type=current_q.question_type or "technical"
            )

            # Persist answer
            ans = Answer(
                interview_id=interview.id,
                question_id=current_q.id,
                candidate_answer_text=candidate_ans
            )
            session.add(ans)
            await session.commit()
            asked_ids.append(current_q.id)

            # Process turn through engine
            state, next_q, is_completed = await engine.process_answer_turn(
                interview=interview,
                state=state,
                last_eval_score=eval_res["overall_question_score"],
                asked_question_ids=asked_ids,
                last_eval_dict=eval_res,
                last_answer_text=candidate_ans
            )

            print(f"Evaluation Score: {eval_res['overall_question_score']}/10.0")
            print(f"Answer Quality: '{eval_res['answer_quality']}'")
            print(f"Recommended Action: '{eval_res['recommended_action']}'")
            print(f"Demonstrated Concepts: {eval_res['demonstrated_concepts']}")
            print(f"Missing Concepts: {eval_res['missing_concepts']}")
            print(f"Misconceptions: {eval_res['misconceptions']}")
            print(f"Feedback: '{eval_res['feedback_text']}'")
            print(f"Adapted Difficulty: '{state.difficulty}'")
            print(f"Interview Stage: '{state.interview_stage}'")
            print(f"Next Stage Topic: '{state.current_topic}'")
            print(f"Session Completed: {is_completed}")
            if next_q:
                print(f"Next Question Text: '{next_q.question_text}'")
                current_q = next_q
            else:
                print("No next question (wrapup reached)")
                break

    print("\n" + "="*80)
    print("LIVE MULTI-TURN TEST FINISHED SUCCESSFULLY")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_live_multi_turn_test())
