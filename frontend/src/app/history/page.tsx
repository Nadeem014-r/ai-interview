"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { InterviewSession } from "@/types";
import { History, Play, FileText, CheckCircle2, Clock, AlertCircle } from "lucide-react";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<InterviewSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadHistory() {
      try {
        const data: any = await apiRequest("/interviews/history");
        setSessions(data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

  return (
    <WorkspaceLayout sectionTitle="Interview History" sectionSubtitle="Archived mock interview sessions and evaluation reports">
      <div style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
          Interview Session Archive
        </h2>
        <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Review detailed evaluation rubrics, question turn history, and recommendations from past interview runs.
        </p>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div className="saas-card skeleton" style={{ height: "60px" }} />
          <div className="saas-card skeleton" style={{ height: "60px" }} />
          <div className="saas-card skeleton" style={{ height: "60px" }} />
        </div>
      ) : sessions.length === 0 ? (
        <div className="saas-card" style={{ padding: "3rem", textAlign: "center" }}>
          <History size={36} color="#a1a1aa" style={{ marginBottom: "0.5rem" }} />
          <h3 style={{ fontSize: "1rem", color: "#09090b" }}>No interviews recorded</h3>
          <p style={{ color: "#71717a", fontSize: "0.85rem", marginBottom: "1.25rem" }}>Launch your first mock interview to generate performance telemetry.</p>
          <Link href="/interview/configure" className="btn btn-primary">
            <Play size={14} /> <span>Start New Interview</span>
          </Link>
        </div>
      ) : (
        <div className="saas-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e4e4e7", color: "#71717a", textAlign: "left", backgroundColor: "#fafafa" }}>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>ID</th>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>Target Role</th>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>Format</th>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>Date</th>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>Status</th>
                  <th style={{ padding: "0.75rem 1rem", fontWeight: 500, textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} style={{ borderBottom: "1px solid #f4f4f5", transition: "background-color 0.15s ease" }}>
                    <td style={{ padding: "0.75rem 1rem", fontWeight: 600, color: "#09090b" }}>#{s.id}</td>
                    <td style={{ padding: "0.75rem 1rem", fontWeight: 500, color: "#09090b" }}>
                      {s.role_title || `Role #${s.role_id}`}
                    </td>
                    <td style={{ padding: "0.75rem 1rem", color: "#71717a", textTransform: "capitalize" }}>
                      {s.interview_type} ({s.mode})
                    </td>
                    <td style={{ padding: "0.75rem 1rem", color: "#71717a" }}>
                      {new Date(s.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
                    </td>
                    <td style={{ padding: "0.75rem 1rem" }}>
                      <span className={`badge ${s.status === "completed" ? "badge-success" : s.status === "in_progress" ? "badge-warning" : "badge-neutral"}`}>
                        {s.status === "completed" ? <CheckCircle2 size={12} /> : <Clock size={12} />} {s.status.replace("_", " ")}
                      </span>
                    </td>
                    <td style={{ padding: "0.75rem 1rem", textAlign: "right" }}>
                      {s.status === "completed" ? (
                        <Link href={`/reports/${s.id}`} className="btn btn-secondary" style={{ padding: "0.3rem 0.65rem", fontSize: "0.78rem" }}>
                          <FileText size={13} /> <span>View Report</span>
                        </Link>
                      ) : (
                        <Link href={`/interview/${s.id}`} className="btn btn-primary" style={{ padding: "0.3rem 0.65rem", fontSize: "0.78rem" }}>
                          <Play size={13} /> <span>Resume</span>
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}
