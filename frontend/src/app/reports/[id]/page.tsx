"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ScoreRadarChart } from "@/components/ScoreRadarChart";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { FinalReport } from "@/types";
import { Award, CheckCircle2, AlertTriangle, Lightbulb, Download, ArrowLeft } from "lucide-react";

export default function CandidateReportPage() {
  const params = useParams();
  const router = useRouter();
  const interviewId = params.id;
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!requireAuth(router)) return;
    async function loadReport() {
      try {
        const data: FinalReport = await apiRequest(`/reports/${interviewId}`);
        setReport(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    if (interviewId) loadReport();
  }, [interviewId]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "#64748b" }}>Generating Final Candidate Report #{interviewId}...</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
        <Navbar />
        <div style={{ textAlign: "center", padding: "4rem" }}>
          <p style={{ color: "#be123c", fontWeight: 600 }}>Report not found for session #{interviewId}.</p>
          <Link href="/dashboard" className="btn btn-secondary" style={{ marginTop: "1rem" }}>Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      <Navbar />

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Top Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.75rem", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <Link href="/dashboard" style={{ color: "#4f46e5", textDecoration: "none", fontSize: "0.85rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.35rem", marginBottom: "0.35rem" }}>
              <ArrowLeft size={16} /> Back to Dashboard
            </Link>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.03em" }}>Final Candidate Performance Report</h1>
            <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Session #{interviewId} • Generated on {new Date(report.created_at).toLocaleDateString()}</span>
          </div>

          <button onClick={() => window.print()} className="btn btn-secondary">
            <Download size={16} /> Print / Export PDF
          </button>
        </div>

        {/* Score Summary Header */}
        <div className="saas-card" style={{ padding: "2.25rem", marginBottom: "1.75rem", backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.5rem" }}>
          <div>
            <div className="badge badge-primary" style={{ marginBottom: "0.5rem" }}>Authoritative AI Evaluation</div>
            <h2 style={{ fontSize: "3rem", fontWeight: 800, color: "#4f46e5", margin: 0, letterSpacing: "-0.03em" }}>
              {report.overall_score} / 100
            </h2>
            <p style={{ color: "#475569", marginTop: "0.5rem", maxWidth: "600px", fontSize: "0.95rem", lineHeight: 1.5 }}>
              {report.executive_summary}
            </p>
          </div>

          <div style={{ backgroundColor: "#f8fafc", padding: "1.5rem 2rem", borderRadius: "14px", border: "1px solid #e2e8f0", textAlign: "center" }}>
            <Award size={44} color="#059669" style={{ marginBottom: "0.35rem" }} />
            <div style={{ fontSize: "0.78rem", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Placement Readiness</div>
            <strong style={{ fontSize: "1.15rem", color: report.overall_score >= 75 ? "#059669" : "#d97706" }}>
              {report.overall_score >= 75 ? "RECOMMENDED" : "NEEDS REVISION"}
            </strong>
          </div>
        </div>

        {/* Charts Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem", marginBottom: "1.75rem" }}>
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", marginBottom: "1rem" }}>Rubric Category Breakdown</h3>
            <ScoreRadarChart scores={report.rubric_scores} />
          </div>
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", marginBottom: "1rem" }}>Topic Mastery Breakdown</h3>
            <ScoreRadarChart scores={report.topic_scores} />
          </div>
        </div>

        {/* Strengths, Weaknesses & Recommendations */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
          {/* Strengths */}
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#047857", marginBottom: "0.85rem" }}>
              <CheckCircle2 size={20} />
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>Key Technical Strengths</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "#475569", fontSize: "0.88rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {report.strengths.map((s, idx) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
          </div>

          {/* Weaknesses */}
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#be123c", marginBottom: "0.85rem" }}>
              <AlertTriangle size={20} />
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>Identified Weaknesses</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "#475569", fontSize: "0.88rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {report.weaknesses.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>

          {/* Recommendations */}
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#b45309", marginBottom: "0.85rem" }}>
              <Lightbulb size={20} />
              <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0 }}>Actionable Study Roadmap</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "#475569", fontSize: "0.88rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {report.recommendations.map((r, idx) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
