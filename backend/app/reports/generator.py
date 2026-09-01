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
            if scores:
                clamped_topic_scores = [max(0.0, min(10.0, float(s))) for s in scores]
                avg_topic_score = sum(clamped_topic_scores) / len(clamped_topic_scores)
                topic_scores[topic] = round(max(0.0, min(10.0, avg_topic_score)), 1)
            else:
                topic_scores[topic] = 0.0

        count = max(1, len(question_scores))
        rubric_scores = {k: round(max(0.0, min(10.0, v / count)), 1) for k, v in rubric_sums.items()}

        # Identify actual weak vs strong topics from scores (0.0 to 10.0 scale)
        strong_topics_list = [t for t, s in topic_scores.items() if s >= 6.0]
        weak_topics_list = [t for t, s in topic_scores.items() if s < 5.5]
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

CRITICAL RULES FOR STRENGTHS AND FEEDBACK:
1. STRICT EVIDENCE-BASED STRENGTHS: A strength may ONLY be reported when there is actual verified evidence in the candidate's answers.
2. NO EVIDENCE = NO STRENGTH: If the candidate answered poorly, gave 1-word/evasive answers (e.g., 'yes', 'no', 'I don't know'), or scored low (overall < 40), DO NOT invent positive strengths. Set:
   "strengths": ["No specific strengths could be identified from the available interview responses."]
3. Return demonstrated technical strengths grounded in the topics where candidate scored well.
4. If the interview terminated early due to low performance, state clearly in executive_summary that the candidate demonstrated insufficient foundational knowledge.

Return JSON:
{{
    "strengths": ["list 1-3 demonstrated candidate strengths"],
    "weaknesses": ["list 2-3 key technical or communication gaps demonstrated"],
    "difficult_topics": ["topics candidate struggled with"],
    "recommendations": ["list 2-3 actionable study/practice recommendations"],
    "executive_summary": "Concise 3-sentence performance overview for placement cell/interview panel."
}}
"""
        try:
            summary_json = await llm.generate_json(prompt)
            if not isinstance(summary_json, dict):
                summary_json = {}
        except Exception:
            summary_json = {}

        # Enforce Evidence-Based Strength Validation Post-Processing
        strengths = summary_json.get("strengths", [])
        if not isinstance(strengths, list):
            strengths = []

        # Filter out generic placeholder strings if candidate performed adequately
        cleaned_strengths = [
            s for s in strengths
            if "insufficient evidence" not in s.lower() and "no specific strengths" not in s.lower()
        ]

        if overall_score >= 40.0 and count > 0:
            if len(cleaned_strengths) > 0:
                strengths = cleaned_strengths[:4]
            else:
                # Synthesize genuine demonstrated strengths from evaluated topics and rubric dimensions
                derived_strengths = []
                for t in strong_topics_list:
                    derived_strengths.append(f"Demonstrated solid understanding of {t} fundamentals")
                if rubric_scores.get("communication", 0) >= 5.5:
                    derived_strengths.append("Clear, structured technical communication and articulation")
                if rubric_scores.get("correctness", 0) >= 5.5:
                    derived_strengths.append("Accurate explanation of core engineering principles")
                if rubric_scores.get("reasoning", 0) >= 5.5:
                    derived_strengths.append("Logical step-by-step problem-solving approach")

                strengths = derived_strengths[:3] if derived_strengths else ["Demonstrated foundational technical knowledge in answered topics."]
        else:
            strengths = ["No specific strengths could be identified from the available interview responses."]

        # Weaknesses post-processing
        weaknesses = summary_json.get("weaknesses", [])
        if not isinstance(weaknesses, list) or len(weaknesses) == 0:
            if weak_topics_list:
                weaknesses = [f"Limited demonstrated depth in {t}" for t in weak_topics_list[:3]]
            else:
                weaknesses = [
                    "Limited demonstrated understanding of foundational concepts.",
                    "Responses were too brief to establish technical knowledge or reasoning."
                ]

        # Recommendations post-processing
        recommendations = summary_json.get("recommendations", [])
        if not isinstance(recommendations, list) or len(recommendations) == 0:
            rec_topics = difficult_topics_list or ["Foundational Computer Science Concepts"]
            recommendations = [
                f"Review core principles and architectural trade-offs in {t}." for t in rec_topics[:2]
            ] + ["Practice articulating technical solutions with structured reasoning in your own words."]

        # Executive summary post-processing
        exec_summary = summary_json.get("executive_summary", "")
        if not exec_summary or "None" in exec_summary:
            if overall_score < 40.0:
                exec_summary = (
                    f"The interview concluded with an overall score of {overall_score}/100. "
                    "The candidate provided brief or non-responsive answers and was unable to demonstrate sufficient foundational knowledge across the assessed competencies."
                )
            elif overall_score >= 75.0:
                exec_summary = (
                    f"The candidate demonstrated strong competence with an overall score of {overall_score}/100. "
                    "They showed clear technical depth, accurate reasoning, and effective structured articulation across target topics."
                )
            else:
                exec_summary = (
                    f"The candidate completed the interview with an overall score of {overall_score}/100. "
                    "They demonstrated baseline foundational familiarity with target areas and will benefit from targeted review of identified growth areas."
                )

        report = Report(
            interview_id=interview_id,
            overall_score=float(overall_score),
            topic_scores=topic_scores,
            rubric_scores=rubric_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            difficult_topics=difficult_topics_list,
            recommendations=recommendations,
            executive_summary=exec_summary
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
