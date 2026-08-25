"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { ScoreRadarChart } from "@/components/ScoreRadarChart";
import { apiRequest } from "@/lib/api";
import { FinalReport } from "@/types";
import { Award, CheckCircle2, AlertTriangle, Lightbulb, Download, ArrowLeft } from "lucide-react";

export default function CandidateReportPage() {
  const params = useParams();
  const interviewId = params.id;
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Generating Final Candidate Report #{interviewId}...</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div style={{ minHeight: "100vh" }}>
        <Navbar />
        <div style={{ textAlign: "center", padding: "4rem" }}>
          <p style={{ color: "var(--accent-rose)" }}>Report not found for session #{interviewId}.</p>
          <Link href="/dashboard" className="btn btn-secondary" style={{ marginTop: "1rem" }}>Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        {/* Top Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
          <div>
            <Link href="/dashboard" style={{ color: "var(--text-muted)", textDecoration: "none", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.5rem" }}>
              <ArrowLeft size={16} /> Back to Dashboard
            </Link>
            <h2>Final Candidate Performance Report</h2>
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Session #{interviewId} • Generated on {new Date(report.created_at).toLocaleDateString()}</span>
          </div>

          <button onClick={() => window.print()} className="btn btn-secondary">
            <Download size={16} /> Print / Export PDF
          </button>
        </div>

        {/* Score Summary Header */}
        <div className="glass-card" style={{ padding: "2.5rem", marginBottom: "2rem", background: "linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(6, 182, 212, 0.2) 100%)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div className="badge badge-primary" style={{ marginBottom: "0.5rem" }}>Authoritative AI Evaluation</div>
            <h1 style={{ fontSize: "3rem", margin: 0, background: "linear-gradient(90deg, #fff, #6ee7b7)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              {report.overall_score} / 100
            </h1>
            <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem", maxWidth: "600px" }}>
              {report.executive_summary}
            </p>
          </div>

          <div style={{ background: "rgba(0,0,0,0.4)", padding: "1.5rem 2rem", borderRadius: "var(--radius-lg)", textAlign: "center" }}>
            <Award size={48} color="var(--accent-emerald)" style={{ marginBottom: "0.5rem" }} />
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Placement Readiness</div>
            <strong style={{ fontSize: "1.1rem", color: "#6ee7b7" }}>
              {report.overall_score >= 75 ? "RECOMMENDED" : "NEEDS REVISION"}
            </strong>
          </div>
        </div>

        {/* Charts Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "2rem" }}>
          <ScoreRadarChart scores={report.rubric_scores} />
          <ScoreRadarChart scores={report.topic_scores} />
        </div>

        {/* Strengths, Weaknesses & Recommendations */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
          {/* Strengths */}
          <div className="glass-card" style={{ padding: "1.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#6ee7b7", marginBottom: "1rem" }}>
              <CheckCircle2 size={22} />
              <h3 style={{ fontSize: "1.1rem" }}>Key Technical Strengths</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "var(--text-secondary)", fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {report.strengths.map((s, idx) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
          </div>

          {/* Weaknesses */}
          <div className="glass-card" style={{ padding: "1.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#fda4af", marginBottom: "1rem" }}>
              <AlertTriangle size={22} />
              <h3 style={{ fontSize: "1.1rem" }}>Identified Weaknesses</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "var(--text-secondary)", fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {report.weaknesses.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>

          {/* Recommendations */}
          <div className="glass-card" style={{ padding: "1.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#fcd34d", marginBottom: "1rem" }}>
              <Lightbulb size={22} />
              <h3 style={{ fontSize: "1.1rem" }}>Actionable Study Roadmap</h3>
            </div>
            <ul style={{ paddingLeft: "1.2rem", color: "var(--text-secondary)", fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {report.recommendations.map((r, idx) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
