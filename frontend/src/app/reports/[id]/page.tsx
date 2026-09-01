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
    if (sessionId) loadReport();
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
          <Link href="/history" style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", color: "#71717a", textDecoration: "none", fontSize: "0.825rem", fontWeight: 500, marginBottom: "0.4rem" }}>
            <ArrowLeft size={14} /> Back to History
          </Link>
          <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
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
          <FileText size={36} color="#a1a1aa" style={{ marginBottom: "0.5rem" }} />
          <h3 style={{ fontSize: "1rem", color: "#09090b" }}>Report Generating or Unavailable</h3>
          <p style={{ color: "#71717a", fontSize: "0.85rem" }}>This session may still be in progress or scoring is being finalized.</p>
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
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#09090b", margin: "0.2rem 0 0.4rem" }}>
                  Executive Placement Evaluation
                </h3>
                <p style={{ color: "#71717a", fontSize: "0.85rem", lineHeight: 1.5, margin: 0 }}>
                  {summaryText}
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", padding: "0.85rem 1.25rem", backgroundColor: "#fafafa", borderRadius: "10px", border: "1px solid #e4e4e7" }}>
                <div style={{ textAlign: "center" }}>
                  <span style={{ fontSize: "0.7rem", color: "#71717a", textTransform: "uppercase", fontWeight: 600, display: "block" }}>Overall Score</span>
                  <div style={{ fontSize: "2.25rem", fontWeight: 800, color: overallScore >= 70 ? "#059669" : overallScore >= 50 ? "#d97706" : "#e11d48", lineHeight: 1 }}>
                    {overallScore}
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "#a1a1aa" }}>out of 100</span>
                </div>
                <div style={{ borderLeft: "1px solid #e4e4e7", paddingLeft: "1.25rem" }}>
                  <span style={{ fontSize: "0.7rem", color: "#71717a", textTransform: "uppercase", fontWeight: 600, display: "block" }}>Readiness</span>
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
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", marginBottom: "1rem" }}>
                Rubric Category Scores
              </h3>
              <ScoreRadarChart scores={rubricScores} />
            </div>

            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", marginBottom: "1rem" }}>
                Topic & Technical Mastery
              </h3>
              <ScoreRadarChart scores={topicMastery} />
            </div>
          </div>

          {/* Qualitative Insights Grid: Strengths, Weaknesses, Recommendations */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem" }}>
            {/* Strengths */}
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.85rem", color: "#059669" }}>
                <CheckCircle2 size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b" }}>Key Strengths</h3>
              </div>
              {strengths.length === 0 ? (
                <p style={{ color: "#a1a1aa", fontSize: "0.825rem" }}>No specific strengths flagged.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "#52525b", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {strengths.map((s: string, idx: number) => (
                    <li key={idx} style={{ lineHeight: 1.5 }}>{s}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Weaknesses */}
            <div className="saas-card" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.85rem", color: "#d97706" }}>
                <AlertTriangle size={18} />
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b" }}>Identified Gaps</h3>
              </div>
              {weaknesses.length === 0 ? (
                <p style={{ color: "#a1a1aa", fontSize: "0.825rem" }}>No critical weaknesses detected.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "#52525b", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
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
                <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b" }}>Actionable Study Roadmap</h3>
              </div>
              {recommendations.length === 0 ? (
                <p style={{ color: "#a1a1aa", fontSize: "0.825rem" }}>No recommendations available.</p>
              ) : (
                <ul style={{ paddingLeft: "1.1rem", margin: 0, fontSize: "0.825rem", color: "#52525b", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {recommendations.map((r: string, idx: number) => (
                    <li key={idx} style={{ lineHeight: 1.5 }}>{r}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}
