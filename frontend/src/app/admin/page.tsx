"use client";

import React, { useEffect, useState } from "react";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { Shield, Globe, Plus, CheckCircle2 } from "lucide-react";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [companyName, setCompanyName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [ingested, setIngested] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAdminData() {
      try {
        const [stData, candData]: [any, any] = await Promise.all([
          apiRequest("/admin/stats").catch(() => null),
          apiRequest("/admin/candidates").catch(() => [])
        ]);
        setStats(stData);
        setCandidates(candData || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAdminData();
  }, []);

  const handleIngestResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngested(false);
    try {
      await apiRequest("/research/company", {
        method: "POST",
        body: JSON.stringify({
          company_name: companyName,
          role_title: roleTitle,
          source_url: sourceUrl
        })
      });
      setIngested(true);
      setCompanyName("");
      setRoleTitle("");
      setSourceUrl("");
      setTimeout(() => setIngested(false), 3000);
    } catch (err) {
      alert("Failed to trigger company research ingestion.");
    }
  };

  return (
    <WorkspaceLayout sectionTitle="Admin Control" sectionSubtitle="University Placement Cell Administration">
      <div style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>
          University Placement & Admin Control Panel
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Manage candidate cohorts and trigger company knowledge ingestion into the RAG vector store.
        </p>
      </div>

      {/* Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1.75rem" }}>
        <div className="saas-card" style={{ padding: "1.25rem" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Registered Candidates</span>
          <h2 style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.25rem" }}>{stats?.total_candidates || 0}</h2>
        </div>
        <div className="saas-card" style={{ padding: "1.25rem" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Total Interviews</span>
          <h2 style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--text-primary)", marginTop: "0.25rem" }}>{stats?.total_interviews || 0}</h2>
        </div>
        <div className="saas-card" style={{ padding: "1.25rem" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>Avg Candidate Score</span>
          <h2 style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--accent-emerald)", marginTop: "0.25rem" }}>{stats?.average_platform_score || 0}</h2>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
        {/* Research Ingestion Card */}
        <div className="saas-card" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "1rem" }}>
            <Globe size={18} color="var(--text-primary)" />
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>Company Research RAG Ingestor</h3>
          </div>

          {ingested && (
            <div style={{ padding: "0.65rem 0.85rem", backgroundColor: "var(--accent-emerald-light)", border: "1px solid rgba(52, 211, 153, 0.32)", borderRadius: "8px", color: "var(--accent-emerald)", fontSize: "0.825rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <CheckCircle2 size={15} /> Job specification chunked & embedded into pgvector RAG store!
            </div>
          )}

          <form onSubmit={handleIngestResearch} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Company Name</label>
              <input type="text" required value={companyName} onChange={(e) => setCompanyName(e.target.value)} className="form-input" placeholder="Google" />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Target Role Title</label>
              <input type="text" required value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} className="form-input" placeholder="Software Engineer (Backend)" />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Official Career / JD URL</label>
              <input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="form-input" placeholder="https://careers.google.com/jobs/results/..." />
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: "0.35rem", fontSize: "0.825rem" }}>
              <Plus size={14} /> <span>Trigger RAG Ingestion Pipeline</span>
            </button>
          </form>
        </div>

        {/* Candidate Table */}
        <div className="saas-card" style={{ padding: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>Registered Candidates</h3>
          <div style={{ overflowY: "auto", maxHeight: "330px" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.825rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left", backgroundColor: "var(--bg-subtle)" }}>
                  <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>ID</th>
                  <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>Name</th>
                  <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>Email</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600, color: "var(--text-primary)" }}>#{c.id}</td>
                    <td style={{ padding: "0.5rem 0.75rem", fontWeight: 500, color: "var(--text-primary)" }}>{c.full_name}</td>
                    <td style={{ padding: "0.5rem 0.75rem", color: "var(--text-muted)" }}>{c.email}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </WorkspaceLayout>
  );
}
