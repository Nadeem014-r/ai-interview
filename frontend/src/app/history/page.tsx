"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { InterviewSession } from "@/types";
import { History, FileText, Play, Plus } from "lucide-react";

export default function InterviewHistoryPage() {
  const [history, setHistory] = useState<InterviewSession[]>([]);

  useEffect(() => {
    async function loadHistory() {
      try {
        const data: any = await apiRequest("/interviews/history");
        setHistory(data || []);
      } catch (err) {
        console.error(err);
      }
    }
    loadHistory();
  }, []);

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
          <div>
            <h2>Interview History & Audit Trail</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
              Complete audit trail of all previous technical, HR, and behavioral interview sessions.
            </p>
          </div>
          <Link href="/interview/configure" className="btn btn-primary">
            <Plus size={16} /> New Session
          </Link>
        </div>

        <div className="glass-card" style={{ padding: "1.5rem", overflowX: "auto" }}>
          {history.length === 0 ? (
            <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>No session history found.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                  <th style={{ padding: "0.75rem 1rem" }}>Session ID</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Target Role & Company</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Type & Mode</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Duration</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Status</th>
                  <th style={{ padding: "0.75rem 1rem" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {history.map((s) => (
                  <tr key={s.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "1rem", fontWeight: 600 }}>#{s.id}</td>
                    <td style={{ padding: "1rem" }}>
                      <div style={{ fontWeight: 500 }}>{s.role_title || `Role #${s.role_id}`}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{s.company_name || "Target Company"}</div>
                    </td>
                    <td style={{ padding: "1rem", textTransform: "capitalize" }}>
                      {s.interview_type || "Technical"} ({s.mode})
                    </td>
                    <td style={{ padding: "1rem" }}>{s.duration_minutes} Mins</td>
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
                          <Play size={14} /> Resume
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

