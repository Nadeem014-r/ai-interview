"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { ScoreRadarChart } from "@/components/ScoreRadarChart";
import { Award, CheckCircle2, AlertTriangle, BookOpen, ArrowLeft, Printer, Sparkles, FileText } from "lucide-react";

export default function ReportDetailPage() {
  const params = useParams();
  const sessionId = params.id;
  const [report, setReport] = useState<any>(null);
  const [turns, setTurns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadReport() {
      try {
        const data: any = await apiRequest(`/reports/${sessionId}`);
        setReport(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    // The per-question record the candidate could not see during the session.
    // It is read from the interview they already own -- the evaluations were
    // computed and stored on each turn, so showing them here costs no provider
    // call and no re-evaluation. A failure here leaves the summary intact.
    async function loadTurns() {
      try {
        const sess: any = await apiRequest(`/interviews/${sessionId}`);
        setTurns(Array.isArray(sess?.answers) ? sess.answers : []);
      } catch (err) {
        console.warn("Per-question breakdown unavailable:", err);
      }
    }

    if (sessionId) {
      loadReport();
      loadTurns();
    }
  }, [sessionId]);

  const handlePrint = () => {
    window.print();
  };

  const overallScore = Math.round(Number(report?.overall_score ?? report?.overall_evaluation?.overall_score ?? 0));
  const strengths = report?.strengths || report?.overall_evaluation?.strengths || [];
  const weaknesses = report?.weaknesses || report?.overall_evaluation?.weaknesses || [];
  const recommendations = report?.recommendations || report?.overall_evaluation?.recommendations || [];
  const rubricScores = report?.rubric_scores || report?.overall_evaluation?.rubric_scores || {};
  const topicMastery = report?.topic_scores || report?.overall_evaluation?.topic_mastery || {};
  const summaryText = report?.executive_summary || report?.overall_evaluation?.summary || "Candidate completed all evaluation turns. Performance calculated against standard industry grading rubrics.";

  return (
    <WorkspaceLayout sectionTitle="Interview Intelligence" sectionSubtitle={`Evaluation Report for Session #${sessionId}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div>
          <Link href="/history" style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", color: "var(--text-muted)", textDecoration: "none", fontSize: "0.825rem", fontWeight: 500, marginBottom: "0.4rem" }}>
            <ArrowLeft size={14} /> Back to History
          </Link>
          <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>
            Candidate Performance Intelligence
          </h2>
        </div>

        <button onClick={handlePrint} className="btn btn-secondary" style={{ fontSize: "0.8rem", padding: "0.4rem 0.85rem" }}>
          <Printer size={13} /> <span>Print / Export PDF</span>
        </button>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="saas-card skeleton" style={{ height: "140px" }} />
          <div className="saas-card skeleton" style={{ height: "200px" }} />
        </div>
      ) : !report ? (
        <div className="saas-card" style={{ padding: "3rem", textAlign: "center" }}>
          <FileText size={36} color="var(--text-tertiary)" style={{ marginBottom: "0.5rem" }} />
          <h3 style={{ fontSize: "1rem", color: "var(--text-primary)" }}>Report Generating or Unavailable</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>This session may still be in progress or scoring is being finalized.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Executive Summary Card */}
          <div className="saas-card" style={{ padding: "1.75rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.5rem" }}>
              <div style={{ maxWidth: "600px" }}>
                <span className="badge badge-neutral" style={{ marginBottom: "0.4rem" }}>
                  <Sparkles size={12} /> Verified AI Assessment
                </span>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", margin: "0.2rem 0 0.4rem" }}>
                  Executive Placement Evaluation
                </h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.5, margin: 0 }}>
                  {summaryText}
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", padding: "0.85rem 1.25rem", backgroundColor: "var(--bg-subtle)", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ textAlign: "center" }}>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, display: "block" }}>Overall Score</span>
                  <div style={{ fontSize: "2.25rem", fontWeight: 800, color: overallScore >= 70 ? "var(--accent-emerald)" : overallScore >= 50 ? "var(--accent-amber)" : "var(--accent-rose)", lineHeight: 1 }}>
                    {overallScore}
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>out of 100</span>
                </div>
                <div style={{ borderLeft: "1px solid var(--border-subtle)", paddingLeft: "1.25rem" }}>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600, display: "block" }}>Readiness</span>
                  <span className={`badge ${overallScore >= 75 ? "badge-success" : overallScore >= 50 ? "badge-warning" : "badge-neutral"}`} style={{ marginTop: "0.25rem" }}>
                    {overallScore >= 75 ? "Placement Ready" : overallScore >= 50 ? "Approaching Ready" : "Developing"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Charts & Rubric Breakdown Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
                Rubric Category Scores
              </h3>
              <ScoreRadarChart scores={rubricScores} />
            </div>

            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
                Topic & Technical Mastery
              </h3>
              <ScoreRadarChart scores={topicMastery} />
            </div>
          </div>

          {/* Qualitative Insights Grid: Strengths, Weaknesses, Recommendations */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem" }}>
            {/* Strengths */}
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.85rem", color: "var(--accent-emerald)" }}>
                <CheckCircle2 size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>Key Strengths</h3>
              </div>
              {strengths.length === 0 ? (
                <p style={{ color: "var(--text-tertiary)", fontSize: "0.825rem" }}>No specific strengths flagged.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {strengths.map((s: string, idx: number) => (
                    <li key={idx} style={{ lineHeight: 1.5 }}>{s}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Weaknesses */}
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.85rem", color: "var(--accent-amber)" }}>
                <AlertTriangle size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>Identified Gaps</h3>
              </div>
              {weaknesses.length === 0 ? (
                <p style={{ color: "var(--text-tertiary)", fontSize: "0.825rem" }}>No critical weaknesses detected.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {weaknesses.map((w: string, idx: number) => (
                    <li key={idx} style={{ lineHeight: 1.5 }}>{w}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Recommendations */}
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.85rem", color: "var(--accent-brand)" }}>
                <BookOpen size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>Actionable Study Roadmap</h3>
              </div>
              {recommendations.length === 0 ? (
                <p style={{ color: "var(--text-tertiary)", fontSize: "0.825rem" }}>No recommendations available.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {recommendations.map((r: string, idx: number) => (
                    <li key={idx} style={{ lineHeight: 1.5 }}>{r}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Per-question record: every question, what was said, and how it was
              assessed. Withheld during the session so the interview stayed a
              conversation; released in full here. */}
          {turns.length > 0 && (
            <div className="saas-card" style={{ padding: "1.5rem", marginTop: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "1rem", color: "var(--accent-brand)" }}>
                <FileText size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
                  Question-by-Question Review ({turns.length})
                </h3>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {turns.map((t: any, idx: number) => {
                  const ev = t.evaluation;
                  return (
                    <div
                      key={t.id ?? idx}
                      style={{
                        padding: "1rem",
                        backgroundColor: "var(--bg-subtle)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "10px",
                        fontSize: "0.825rem"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
                        <strong style={{ color: "var(--text-primary)", lineHeight: 1.45 }}>
                          Q{idx + 1}: {t.question_text}
                        </strong>
                        {ev?.overall_question_score !== undefined && ev?.overall_question_score !== null && (
                          <span className="badge badge-neutral" style={{ whiteSpace: "nowrap", height: "fit-content" }}>
                            {Number(ev.overall_question_score).toFixed(1)} / 10
                          </span>
                        )}
                      </div>

                      <p style={{ margin: "0 0 0.6rem", color: "var(--text-secondary)", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                        <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Your answer: </span>
                        {t.candidate_answer_text}
                      </p>

                      {ev?.feedback_text && (
                        <p style={{ margin: "0 0 0.6rem", color: "var(--accent-emerald)", lineHeight: 1.5 }}>
                          <span style={{ fontWeight: 600 }}>Assessment: </span>
                          {ev.feedback_text}
                        </p>
                      )}

                      {Array.isArray(ev?.evidence) && ev.evidence.length > 0 && (
                        <ul style={{ margin: "0 0 0.6rem", paddingLeft: "1.1rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                          {ev.evidence.map((e: string, i: number) => (
                            <li key={i} style={{ lineHeight: 1.45 }}>{e}</li>
                          ))}
                        </ul>
                      )}

                      {ev && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                          {[
                            ["Correctness", ev.correctness_score],
                            ["Relevance", ev.relevance_score],
                            ["Reasoning", ev.reasoning_score],
                            ["Depth", ev.depth_score],
                            ["Communication", ev.communication_score]
                          ]
                            .filter(([, v]) => v !== undefined && v !== null)
                            .map(([label, v]) => (
                              <span key={String(label)} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>
                                {label}: {Number(v).toFixed(1)}
                              </span>
                            ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </WorkspaceLayout>
  );
}
