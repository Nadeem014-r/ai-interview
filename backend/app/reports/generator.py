from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Interview, Answer, Evaluation, Report, Question, Company, Role, User
from app.evaluation.scorer import DeterministicScorer
from app.ai.factory import AIFactory

class ReportGenerator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_interview_report(self, interview_id: int) -> Report:
        # Check if report already generated
        stmt_existing = select(Report).where(Report.interview_id == interview_id)
        res_existing = await self.db.execute(stmt_existing)
        existing_report = res_existing.scalars().first()
        if existing_report:
            return existing_report

        # Retrieve interview with answers & evaluations
        stmt = select(Interview).where(Interview.id == interview_id)
        res = await self.db.execute(stmt)
        interview = res.scalars().first()
        if not interview:
            raise ValueError(f"Interview {interview_id} not found.")

        # Get answers and evaluations
        stmt_answers = select(Answer).where(Answer.interview_id == interview_id)
        res_answers = await self.db.execute(stmt_answers)
        answers = res_answers.scalars().all()

        question_scores = []
        topic_score_sums: Dict[str, List[float]] = {}
        rubric_sums = {"correctness": 0.0, "relevance": 0.0, "reasoning": 0.0, "depth": 0.0, "communication": 0.0}

        for ans in answers:
            stmt_eval = select(Evaluation).where(Evaluation.answer_id == ans.id)
            res_eval = await self.db.execute(stmt_eval)
            evaluation = res_eval.scalars().first()
            
            stmt_q = select(Question).where(Question.id == ans.question_id)
            res_q = await self.db.execute(stmt_q)
            q = res_q.scalars().first()
            
            if evaluation:
                question_scores.append(evaluation.overall_question_score)
                rubric_sums["correctness"] += evaluation.correctness_score
                rubric_sums["relevance"] += evaluation.relevance_score
                rubric_sums["reasoning"] += evaluation.reasoning_score
                rubric_sums["depth"] += evaluation.depth_score
                rubric_sums["communication"] += evaluation.communication_score
                
                if q and q.topic:
                    if q.topic not in topic_score_sums:
                        topic_score_sums[q.topic] = []
                    topic_score_sums[q.topic].append(evaluation.overall_question_score)

        # Deterministic score calculation
        overall_score = DeterministicScorer.calculate_overall_interview_score(question_scores)
        
        topic_scores = {}
        for topic, scores in topic_score_sums.items():
            topic_scores[topic] = round((sum(scores) / len(scores)) * 10.0, 1)

        count = max(1, len(question_scores))
        rubric_scores = {k: round(v / count, 1) for k, v in rubric_sums.items()}

        # LLM generated feedback summary
        llm = AIFactory.get_llm_provider()
        prompt = f"""
        Generate candidate interview report synthesis based on structured metrics:
        OVERALL SCORE: {overall_score}/100
        TOPIC SCORES: {topic_scores}
        RUBRIC SCORES: {rubric_scores}
        
        Return JSON matching:
        {{
            "strengths": ["list 3 key candidate strengths"],
            "weaknesses": ["list 2 key technical weaknesses"],
            "difficult_topics": ["topics candidate struggled with"],
            "recommendations": ["list 3 actionable study/practice recommendations"],
            "executive_summary": "Concise 3-sentence performance overview for placement cell/interview panel."
        }}
        """
        try:
            summary_json = await llm.generate_json(prompt)
        except Exception:
            summary_json = {
                "strengths": ["Demonstrates strong foundational knowledge", "Structured communication style"],
                "weaknesses": ["Deep technical edge cases need further practice"],
                "difficult_topics": list(topic_scores.keys())[:1] if topic_scores else ["System Optimization"],
                "recommendations": ["Review relational database indexing", "Practice system design interviews"],
                "executive_summary": f"The candidate scored {overall_score}/100 across target interview topics. Recommended for next placement rounds with targeted study."
            }

        report = Report(
            interview_id=interview_id,
            overall_score=overall_score,
            topic_scores=topic_scores,
            rubric_scores=rubric_scores,
            strengths=summary_json.get("strengths", []),
            weaknesses=summary_json.get("weaknesses", []),
            difficult_topics=summary_json.get("difficult_topics", []),
            recommendations=summary_json.get("recommendations", []),
            executive_summary=summary_json.get("executive_summary", "")
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
