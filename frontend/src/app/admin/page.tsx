"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { Shield, Users, Building, FileCheck, Globe, Plus, CheckCircle2 } from "lucide-react";

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
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
          <Shield size={28} color="var(--primary)" />
          <h2>University Placement Cell & Admin Control Panel</h2>
        </div>

        {/* Stats Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.25rem", marginBottom: "2.5rem" }}>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Registered Candidates</span>
            <h2 style={{ fontSize: "2rem", color: "var(--primary)", marginTop: "0.4rem" }}>{stats?.total_candidates || 0}</h2>
          </div>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Total Interviews</span>
            <h2 style={{ fontSize: "2rem", color: "var(--accent-cyan)", marginTop: "0.4rem" }}>{stats?.total_interviews || 0}</h2>
          </div>
          <div className="glass-card" style={{ padding: "1.25rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Avg Candidate Score</span>
            <h2 style={{ fontSize: "2rem", color: "var(--accent-emerald)", marginTop: "0.4rem" }}>{stats?.average_platform_score || 0}</h2>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
          {/* Research Ingestion Card */}
          <div className="glass-card" style={{ padding: "1.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.25rem" }}>
              <Globe size={20} color="var(--accent-cyan)" />
              <h3>Company Research RAG Ingestor</h3>
            </div>

            {ingested && (
              <div style={{ padding: "0.75rem 1rem", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "var(--radius-md)", color: "#6ee7b7", fontSize: "0.85rem", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <CheckCircle2 size={16} /> Job specification chunked & embedded into pgvector RAG store!
              </div>
            )}

            <form onSubmit={handleIngestResearch} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Company Name</label>
                <input type="text" required value={companyName} onChange={(e) => setCompanyName(e.target.value)} className="form-input" placeholder="Google" />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Target Role Title</label>
                <input type="text" required value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} className="form-input" placeholder="Software Engineer (Backend)" />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Official Career / JD URL</label>
                <input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="form-input" placeholder="https://careers.google.com/jobs/results/..." />
              </div>
              <button type="submit" className="btn btn-primary" style={{ marginTop: "0.5rem" }}>
                <Plus size={16} /> Trigger RAG Ingestion Pipeline
              </button>
            </form>
          </div>

          {/* Candidate Table */}
          <div className="glass-card" style={{ padding: "1.75rem" }}>
            <h3 style={{ marginBottom: "1.25rem" }}>Registered Candidates</h3>
            <div style={{ overflowY: "auto", maxHeight: "350px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)", textAlign: "left" }}>
                    <th style={{ padding: "0.5rem" }}>ID</th>
                    <th style={{ padding: "0.5rem" }}>Name</th>
                    <th style={{ padding: "0.5rem" }}>Email</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "0.5rem" }}>#{c.id}</td>
                      <td style={{ padding: "0.5rem", fontWeight: 600 }}>{c.full_name}</td>
                      <td style={{ padding: "0.5rem", color: "var(--text-secondary)" }}>{c.email}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
