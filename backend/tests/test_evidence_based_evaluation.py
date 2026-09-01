import pytest
from app.evaluation.evaluator import AnswerEvaluator
from app.evaluation.validation import is_minimal_or_non_substantive_response, classify_response_quality_state
from app.reports.generator import ReportGenerator
from app.evaluation.scorer import DeterministicScorer
from app.db.models import User, Company, Role, Interview, Question, Answer, Evaluation
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from datetime import datetime


@pytest.mark.asyncio
async def test_minimal_answers_evaluation_scores_and_no_fabricated_concepts():
    """TEST A: Candidate answering 'yes', 'no', 'no' receives low scores and zero demonstrated concepts."""
    # 1. Validation classification
    assert is_minimal_or_non_substantive_response("yes") is True
    assert is_minimal_or_non_substantive_response("no") is True
    assert is_minimal_or_non_substantive_response("ok") is True
    assert classify_response_quality_state("yes", "Database Indexing", ["B-Trees", "I/O reduction"]) == "MINIMAL_NON_SUBSTANTIVE"

    # 2. Evaluation
    res = await AnswerEvaluator.evaluate_answer(
        question_text="How do database indexes optimize query execution?",
        expected_concepts=["B-Trees", "Disk I/O reduction"],
        candidate_answer="yes",
        topic="Database Indexing",
        question_type="technical"
    )

    assert res["correctness"] == 0.0
    assert res["relevance"] == 0.0
    assert res["reasoning"] == 0.0
    assert res["depth"] == 0.0
    assert res["communication"] <= 2.0
    assert res["overall_question_score"] <= 1.0
    assert len(res["demonstrated_concepts"]) == 0
    assert res["answer_quality"] == "unknown"
    assert res["recommended_action"] == "recover"


@pytest.mark.asyncio
async def test_detailed_technical_answer_demonstrates_real_strengths():
    """TEST B: Detailed technical answers receive high scores and valid demonstrated concepts."""
    detailed_ans = (
        "Database indexes commonly use B+ Trees because all leaf nodes are at the same depth and linked sequentially. "
        "This minimizes disk I/O seek operations from O(N) to O(log N) and enables efficient range scans."
    )
    res = await AnswerEvaluator.evaluate_answer(
        question_text="How do database indexes optimize query execution?",
        expected_concepts=["B-Trees", "Disk I/O reduction", "Time complexity"],
        candidate_answer=detailed_ans,
        topic="Database Indexing",
        question_type="technical"
    )

    assert res["correctness"] >= 7.0
    assert res["relevance"] >= 7.0
    assert res["overall_question_score"] >= 6.5
    assert len(res["demonstrated_concepts"]) > 0


@pytest.mark.asyncio
async def test_poor_interview_report_never_fabricates_strengths():
    """TEST A & D: Poor candidate performance ('yes', 'no', 'no') produces no fabricated strengths."""
    async with AsyncSessionLocal() as session:
        # Setup test entities
        ts = datetime.utcnow().timestamp()
        user = User(
            email=f"poor_eval_{ts}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Poor Candidate",
            role="candidate"
        )
        company = Company(name=f"Meta_{ts}", slug=f"meta_{ts}", culture_keywords=["Move Fast"])
        session.add_all([user, company])
        await session.commit()
        await session.refresh(user)
        await session.refresh(company)

        role = Role(company_id=company.id, title="Backend Engineer", level="Junior", required_skills=["Python", "FastAPI"])
        session.add(role)
        await session.commit()
        await session.refresh(role)

        interview = Interview(
            candidate_id=user.id,
            company_id=company.id,
            role_id=role.id,
            mode="text",
            duration_minutes=30,
            target_level="entry",
            status="completed"
        )
        session.add(interview)
        await session.commit()
        await session.refresh(interview)

        # 3 Turns of minimal answers
        turns = [
            ("Tell me about yourself.", "yes", "Introduction"),
            ("How does FastAPI handle async requests?", "no", "FastAPI Concurrency"),
            ("What are B-Tree index trade-offs?", "no", "Database Indexing")
        ]

        for q_text, ans_text, topic in turns:
            q = Question(
                company_id=company.id,
                role_id=role.id,
                topic=topic,
                question_text=q_text,
                difficulty="easy",
                question_type="technical"
            )
            session.add(q)
            await session.commit()
            await session.refresh(q)

            eval_res = await AnswerEvaluator.evaluate_answer(
                question_text=q_text,
                expected_concepts=["Core concepts"],
                candidate_answer=ans_text,
                topic=topic,
                question_type="technical"
            )

            ans = Answer(
                interview_id=interview.id,
                question_id=q.id,
                candidate_answer_text=ans_text
            )
            session.add(ans)
            await session.commit()
            await session.refresh(ans)

            evaluation = Evaluation(
                answer_id=ans.id,
                correctness_score=eval_res["correctness_score"],
                relevance_score=eval_res["relevance_score"],
                reasoning_score=eval_res["reasoning_score"],
                depth_score=eval_res["depth_score"],
                communication_score=eval_res["communication_score"],
                overall_question_score=eval_res["overall_question_score"],
                feedback_text=eval_res["feedback_text"],
                evidence=eval_res["evidence"]
            )
            session.add(evaluation)
            await session.commit()

        # Generate Report
        report_gen = ReportGenerator(session)
        report = await report_gen.generate_interview_report(interview.id)

        assert report.overall_score <= 15.0
        for t_score in report.topic_scores.values():
            assert 0.0 <= t_score <= 10.0

        # Ensure NO fabricated strengths
        assert len(report.strengths) > 0
        assert any("insufficient" in s.lower() for s in report.strengths)
        assert not any("strong communication" in s.lower() for s in report.strengths)
        assert not any("fastapi" in s.lower() for s in report.strengths)
        assert not any("demonstrated solid grasp" in s.lower() for s in report.strengths)

        # Ensure honest executive summary
        assert "insufficient" in report.executive_summary.lower() or "unable" in report.executive_summary.lower() or "gaps" in report.executive_summary.lower()


def test_score_ranges_and_deterministic_scorer():
    """TEST G: Validate deterministic scoring math and bounds."""
    q_scores = [0.1, 0.1, 0.2]
    overall = DeterministicScorer.calculate_overall_interview_score(q_scores)
    assert 0.0 <= overall <= 100.0
    assert overall < 5.0

    perfect_scores = [10.0, 10.0, 10.0]
    assert DeterministicScorer.calculate_overall_interview_score(perfect_scores) == 100.0
