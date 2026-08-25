"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { InterviewSession, Company, JobMatchResult, ResumeItem } from "@/types";
import { Play, FileText, History, Award, Building, Plus, Sparkles, CheckCircle2, AlertCircle, ArrowRight } from "lucide-react";

export default function DashboardPage() {
  const [history, setHistory] = useState<InterviewSession[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const [histData, compData, matchData, resData]: [any, any, any, any] = await Promise.all([
          apiRequest("/interviews/history").catch(() => []),
          apiRequest("/companies").catch(() => []),
          apiRequest("/jobs/matches").catch(() => []),
          apiRequest("/resume").catch(() => [])
        ]);
        setHistory(histData || []);
        setCompanies(compData || []);
        setMatches(matchData || []);
        setResumes(resData || []);
      } catch (err) {
        console.error("Dashboard fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  const completedSessions = history.filter((s) => s.status === "completed");
  const hasResume = resumes.length > 0;

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        {/* Banner */}
        <div className="glass-card" style={{ padding: "2rem", marginBottom: "2rem", background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(6, 182, 212, 0.15) 100%)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <h1 style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>Candidate Placement & AI Dashboard</h1>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                AI-driven resume intelligence, role compatibility scoring, and adaptive mock interviews.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <Link href="/resume" className="btn btn-secondary" style={{ padding: "0.85rem 1.25rem" }}>
                <FileText size={18} /> {hasResume ? "View Resume" : "Upload Resume"}
              </Link>
              <Link href="/interview/configure" className="btn btn-primary" style={{ padding: "0.85rem 1.25rem" }}>
                <Plus size={18} /> Launch Mock Interview
              </Link>
            </div>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.25rem", marginBottom: "2.5rem" }}>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Completed Sessions</span>
            <h2 style={{ fontSize: "2rem", color: "var(--accent-cyan)", margin: "0.4rem 0 0" }}>{completedSessions.length}</h2>
          </div>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Total Interviews</span>
            <h2 style={{ fontSize: "2rem", color: "var(--primary)", margin: "0.4rem 0 0" }}>{history.length}</h2>
          </div>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Resume Intelligence</span>
            <h2 style={{ fontSize: "1.25rem", color: hasResume ? "var(--accent-emerald)" : "var(--accent-rose)", margin: "0.6rem 0 0" }}>
              {hasResume ? "Profile Parsed" : "Resume Missing"}
            </h2>
          </div>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Available Roles</span>
            <h2 style={{ fontSize: "2rem", color: "var(--accent-emerald)", margin: "0.4rem 0 0" }}>{matches.length}</h2>
          </div>
        </div>

        {/* Top Recommended Job Descriptions Section */}
        {matches.length > 0 && (
          <div style={{ marginBottom: "3rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <div>
                <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Sparkles size={20} color="var(--primary)" /> Top Recommended Job Roles & Match Scores
                </h3>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Calculated against your uploaded resume and candidate skills profile
                </span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1.25rem" }}>
              {matches.slice(0, 3).map((m) => (
                <div key={m.role_id} className="glass-card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                      <div>
                        <h4 style={{ fontSize: "1.15rem", margin: 0 }}>{m.role_title}</h4>
                        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{m.company_name} • {m.role_level}</span>
                      </div>
                      <span className="badge badge-success" style={{ fontSize: "0.85rem", fontWeight: 700 }}>
                        {m.overall_score}% Match
                      </span>
                    </div>

                    <div style={{ marginBottom: "1rem" }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "0.4rem" }}>Matched Skills:</span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                        {m.matched_skills.map((s) => (
                          <span key={s} className="badge badge-primary" style={{ fontSize: "0.7rem" }}>{s}</span>
                        ))}
                      </div>
                    </div>

                    {m.missing_skills.length > 0 && (
                      <div style={{ marginBottom: "1rem" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--accent-rose)", textTransform: "uppercase", display: "block", marginBottom: "0.4rem" }}>Skill Gaps to Target:</span>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                          {m.missing_skills.map((s) => (
                            <span key={s} className="badge badge-warning" style={{ fontSize: "0.7rem" }}>{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <Link href={`/interview/configure?company_id=${m.company_id}&role_id=${m.role_id}`} className="btn btn-primary" style={{ width: "100%", justifyContent: "center", marginTop: "1rem" }}>
                    <Play size={14} /> Practice Mock Interview
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Target Companies Section */}
        <div style={{ marginBottom: "3rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <h3>Target Placement Catalog</h3>
            <Link href="/companies" style={{ color: "var(--primary)", textDecoration: "none", fontSize: "0.9rem" }}>View All Companies</Link>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.25rem" }}>
            {companies.map((c) => (
              <div key={c.id} className="glass-card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
                    <Building size={24} color="var(--primary)" />
                    <h4 style={{ fontSize: "1.1rem", margin: 0 }}>{c.name}</h4>
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem", lineHeight: 1.4 }}>{c.description}</p>
                </div>
                <Link href={`/companies/${c.id}/roles`} className="btn btn-secondary" style={{ width: "100%", justifyContent: "center" }}>
                  View Roles & Requirements
                </Link>
              </div>
            ))}
          </div>
        </div>

        {/* Recent History Table */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <h3>Recent Interview Sessions</h3>
            <Link href="/history" style={{ color: "var(--primary)", textDecoration: "none", fontSize: "0.9rem" }}>Full History</Link>
          </div>

          {history.length === 0 ? (
            <div className="glass-card" style={{ textAlign: "center", padding: "3rem" }}>
              <History size={36} color="var(--text-muted)" style={{ marginBottom: "1rem" }} />
              <p style={{ color: "var(--text-secondary)" }}>No interview sessions taken yet.</p>
              <Link href="/interview/configure" className="btn btn-primary" style={{ marginTop: "1rem" }}>Launch Your First Session</Link>
            </div>
          ) : (
            <div className="glass-card" style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                    <th style={{ padding: "1rem" }}>Session ID</th>
                    <th style={{ padding: "1rem" }}>Target Role</th>
                    <th style={{ padding: "1rem" }}>Type & Mode</th>
                    <th style={{ padding: "1rem" }}>Status</th>
                    <th style={{ padding: "1rem" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 5).map((s) => (
                    <tr key={s.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "1rem", fontWeight: 600 }}>#{s.id}</td>
                      <td style={{ padding: "1rem" }}>{s.role_title || `Role #${s.role_id}`} ({s.company_name || "Company"})</td>
                      <td style={{ padding: "1rem", textTransform: "capitalize" }}>{s.interview_type || "Technical"} ({s.mode})</td>
                      <td style={{ padding: "1rem" }}>
                        <span className={`badge ${s.status === "completed" ? "badge-success" : "badge-warning"}`}>
                          {s.status}
                        </span>
                      </td>
                      <td style={{ padding: "1rem" }}>
                        {s.status === "completed" ? (
                          <Link href={`/reports/${s.id}`} className="btn btn-secondary" style={{ padding: "0.35rem 0.8rem", fontSize: "0.8rem" }}>
                            <FileText size={14} /> View Report
                          </Link>
                        ) : (
                          <Link href={`/interview/${s.id}`} className="btn btn-primary" style={{ padding: "0.35rem 0.8rem", fontSize: "0.8rem" }}>
                            <Play size={14} /> Resume Session
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

