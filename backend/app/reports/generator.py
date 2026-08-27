from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Interview, Answer, Evaluation, Report, Question, Company, Role, User
from app.evaluation.scorer import DeterministicScorer
from app.ai.factory import AIFactory


class ReportGenerator:
    """Evidence-based report generator grounded in candidate interview turns."""

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
        evidence_records: List[str] = []

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

                topic_name = q.topic if (q and q.topic) else "General Technical"
                if topic_name not in topic_score_sums:
                    topic_score_sums[topic_name] = []
                topic_score_sums[topic_name].append(evaluation.overall_question_score)

                if evaluation.evidence:
                    for ev in evaluation.evidence:
                        evidence_records.append(f"[{topic_name} (Score: {evaluation.overall_question_score}/10)] {ev}")

        # Deterministic score calculation
        overall_score = DeterministicScorer.calculate_overall_interview_score(question_scores)

        topic_scores = {}
        for topic, scores in topic_score_sums.items():
            topic_scores[topic] = round((sum(scores) / len(scores)) * 10.0, 1)

        count = max(1, len(question_scores))
        rubric_scores = {k: round(v / count, 1) for k, v in rubric_sums.items()}

        # Identify actual weak vs strong topics from scores
        strong_topics_list = [t for t, s in topic_scores.items() if s >= 75.0]
        weak_topics_list = [t for t, s in topic_scores.items() if s < 60.0]
        difficult_topics_list = weak_topics_list if weak_topics_list else ([min(topic_scores, key=topic_scores.get)] if topic_scores else [])

        # LLM generated feedback summary grounded in evidence
        llm = AIFactory.get_llm_provider()
        prompt = f"""
Generate an executive candidate interview assessment report grounded strictly in the interview metrics and evidence.

INTERVIEW OVERALL SCORE: {overall_score}/100
TOPIC BREAKDOWN SCORES: {topic_scores}
DIMENSION RUBRIC SCORES (0-10): {rubric_scores}

OBSERVED INTERVIEW EVIDENCE:
{evidence_records[:6] if evidence_records else "Standard technical viva interview."}

RULES:
1. Ground all strengths and weaknesses strictly in the topics assessed during this interview.
2. DO NOT invent or fabricate candidate achievements or knowledge not demonstrated in the evidence.
3. If a topic was scored poorly, reflect it as a knowledge gap or area for improvement.
4. Recommendations must be actionable study topics directly related to the weak areas.

Return JSON:
{{
    "strengths": ["list 2-3 key demonstrated candidate strengths"],
    "weaknesses": ["list 2 key technical or communication gaps"],
    "difficult_topics": ["topics candidate struggled with"],
    "recommendations": ["list 2-3 actionable study/practice recommendations"],
    "executive_summary": "Concise 3-sentence performance overview for placement cell/interview panel."
}}
"""
        try:
            summary_json = await llm.generate_json(prompt)
        except Exception:
            strengths_fallback = [f"Demonstrated solid grasp of {t}" for t in strong_topics_list] if strong_topics_list else ["Structured problem-solving communication"]
            weaknesses_fallback = [f"Need deeper exploration of {t} trade-offs" for t in weak_topics_list] if weak_topics_list else ["Deep edge-case handling needs practice"]
            recommendations_fallback = [f"Review advanced architectural trade-offs in {t}" for t in (difficult_topics_list or ["System Design"])]

            summary_json = {
                "strengths": strengths_fallback[:3],
                "weaknesses": weaknesses_fallback[:2],
                "difficult_topics": difficult_topics_list[:2],
                "recommendations": recommendations_fallback[:3],
                "executive_summary": f"The candidate achieved an overall score of {overall_score}/100 across assessed interview competencies. Recommended for placement rounds with targeted practice on identified areas."
            }

        report = Report(
            interview_id=interview_id,
            overall_score=overall_score,
            topic_scores=topic_scores,
            rubric_scores=rubric_scores,
            strengths=summary_json.get("strengths", []),
            weaknesses=summary_json.get("weaknesses", []),
            difficult_topics=summary_json.get("difficult_topics", difficult_topics_list),
            recommendations=summary_json.get("recommendations", []),
            executive_summary=summary_json.get("executive_summary", "")
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
