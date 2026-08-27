"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { Company, Role } from "@/types";
import { Settings, Play, Sliders } from "lucide-react";

function ConfigureInterviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCompanyId = searchParams.get("company_id") || "1";
  const initialRoleId = searchParams.get("role_id") || "1";
  const initialMode = searchParams.get("mode") || "text";

  const [companies, setCompanies] = useState<Company[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [companyId, setCompanyId] = useState(initialCompanyId);
  const [roleId, setRoleId] = useState(initialRoleId);
  const [interviewType, setInterviewType] = useState("technical"); // technical, hr, behavioral, role_specific, mixed
  const [mode, setMode] = useState(initialMode); // text, audio, video
  const [duration, setDuration] = useState(30); // 10, 15, 30, 45, 60
  const [level, setLevel] = useState("entry");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!requireAuth(router)) return;
    async function loadCompanies() {
      try {
        const comps: any = await apiRequest("/companies");
        setCompanies(comps || []);
        if (comps && comps.length > 0 && !companyId) {
          setCompanyId(String(comps[0].id));
        }
      } catch (err) {
        console.error(err);
      }
    }
    loadCompanies();
  }, []);

  useEffect(() => {
    async function loadRoles() {
      if (!companyId) return;
      try {
        const rData: any = await apiRequest(`/companies/${companyId}/roles`);
        setRoles(rData || []);
        if (rData && rData.length > 0) {
          setRoleId(String(rData[0].id));
        }
      } catch (err) {
        console.error(err);
      }
    }
    loadRoles();
  }, [companyId]);

  const handleStartInterview = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res: any = await apiRequest("/interviews", {
        method: "POST",
        body: JSON.stringify({
          company_id: parseInt(companyId),
          role_id: parseInt(roleId),
          mode,
          interview_type: interviewType,
          duration_minutes: duration,
          target_level: level
        })
      });
      router.push(`/interview/${res.id}`);
    } catch (err: any) {
      alert(err.message || "Failed to launch interview session.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      <Navbar />

      <main style={{ maxWidth: "750px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div className="saas-card" style={{ padding: "2.25rem", backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <div style={{ backgroundColor: "#eef2ff", padding: "0.5rem", borderRadius: "10px", color: "#4f46e5" }}>
              <Sliders size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.03em" }}>Interview Configuration</h1>
              <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Customize company role, interview rubric type, and interaction mode</span>
            </div>
          </div>

          <form onSubmit={handleStartInterview} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {/* Target Company */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Target Company</label>
              <select value={companyId} onChange={(e) => setCompanyId(e.target.value)} className="form-input">
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* Target Role */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Job Role</label>
              <select value={roleId} onChange={(e) => setRoleId(e.target.value)} className="form-input">
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>{r.title} ({r.level})</option>
                ))}
              </select>
            </div>

            {/* Interview Type Selection */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Interview Type</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "0.5rem" }}>
                {[
                  { id: "technical", label: "Technical" },
                  { id: "hr", label: "HR / Fit" },
                  { id: "behavioral", label: "Behavioral" },
                  { id: "role_specific", label: "Role-Specific" },
                  { id: "mixed", label: "Mixed" }
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setInterviewType(t.id)}
                    className={`btn ${interviewType === t.id ? "btn-primary" : "btn-secondary"}`}
                    style={{ padding: "0.45rem", justifyContent: "center", fontSize: "0.82rem" }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Seniority */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Target Experience Level</label>
              <select value={level} onChange={(e) => setLevel(e.target.value)} className="form-input">
                <option value="entry">Entry Level / Final Year B.Tech</option>
                <option value="mid">Mid Level (1-3 Years Experience)</option>
                <option value="senior">Senior Level (3+ Years Experience)</option>
              </select>
            </div>

            {/* Mode selection */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Interview Interaction Mode</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                {["text", "audio", "video"].map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m)}
                    className={`btn ${mode === m ? "btn-primary" : "btn-secondary"}`}
                    style={{ textTransform: "capitalize", justifyContent: "center", padding: "0.6rem" }}
                  >
                    {m} Interview
                  </button>
                ))}
              </div>
            </div>

            {/* Duration selection */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.35rem" }}>Session Duration</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem" }}>
                {[10, 15, 30, 45, 60].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDuration(d)}
                    className={`btn ${duration === d ? "btn-primary" : "btn-secondary"}`}
                    style={{ padding: "0.45rem", justifyContent: "center", fontSize: "0.82rem" }}
                  >
                    {d} Mins
                  </button>
                ))}
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ padding: "0.85rem", marginTop: "0.75rem", fontSize: "0.95rem" }}>
              <Play size={18} /> {loading ? "Initializing Engine..." : "Start Adaptive Interview"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

export default function ConfigureInterviewPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}>Loading configuration...</div>}>
      <ConfigureInterviewContent />
    </Suspense>
  );
}
