"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { Company, Role } from "@/types";
import { Play, Building2, Briefcase } from "lucide-react";

function ConfigureInterviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [companies, setCompanies] = useState<Company[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | undefined>();
  const [selectedRoleId, setSelectedRoleId] = useState<number | undefined>();
  const [matchData, setMatchData] = useState<any>(null);
  const [mode, setMode] = useState<string>("text");
  const [duration, setDuration] = useState<number>(15);
  const [loading, setLoading] = useState(false);
  const [fetchingData, setFetchingData] = useState(true);

  useEffect(() => {
    if (requireAuth(router)) {
      loadInitialData();
    }
  }, []);

  async function loadInitialData() {
    try {
      const compData: any = await apiRequest("/companies");
      setCompanies(compData || []);

      const qCompanyId = searchParams.get("company_id");
      const qRoleId = searchParams.get("role_id");
      const qMode = searchParams.get("mode");

      if (qMode && ["text", "audio", "video"].includes(qMode)) {
        setMode(qMode);
      }

      let activeRoleId: number | undefined;

      if (qCompanyId) {
        const cIdNum = Number(qCompanyId);
        setSelectedCompanyId(cIdNum);
        const rolesData: any = await apiRequest(`/companies/${qCompanyId}/roles`);
        setRoles(rolesData || []);
        if (qRoleId) {
          activeRoleId = Number(qRoleId);
          setSelectedRoleId(activeRoleId);
        } else if (rolesData && rolesData.length > 0) {
          activeRoleId = rolesData[0].id;
          setSelectedRoleId(activeRoleId);
        }
      } else if (compData && compData.length > 0) {
        const defaultCompanyId = compData[0].id;
        setSelectedCompanyId(defaultCompanyId);
        const rolesData: any = await apiRequest(`/companies/${defaultCompanyId}/roles`);
        setRoles(rolesData || []);
        if (rolesData && rolesData.length > 0) {
          activeRoleId = rolesData[0].id;
          setSelectedRoleId(activeRoleId);
        }
      }

      if (activeRoleId) {
        loadRoleMatch(activeRoleId);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setFetchingData(false);
    }
  }

  const loadRoleMatch = async (roleId: number) => {
    try {
      const match = await apiRequest(`/jobs/matches/${roleId}`).catch(() => null);
      setMatchData(match);
    } catch {
      setMatchData(null);
    }
  };

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);
  const selectedRole = roles.find((r) => r.id === selectedRoleId);

  const handleStartInterview = async () => {
    if (!selectedCompanyId || !selectedRoleId) {
      alert("Please select a target company and job role to configure the interview questions.");
      return;
    }

    if (matchData && matchData.is_eligible === false) {
      alert("Your profile needs a little more information before starting this role-specific interview. Please update your resume or profile.");
      return;
    }

    setLoading(true);
    try {
      const res: any = await apiRequest("/interviews", {
        method: "POST",
        body: JSON.stringify({
          company_id: Number(selectedCompanyId),
          role_id: Number(selectedRoleId),
          interview_type: "technical",
          mode: mode,
          duration_minutes: Number(duration),
          target_level: selectedRole?.level || "junior",
        }),
      });

      router.push(`/interview/${res.id}`);
    } catch (err: any) {
      alert(err.message || "Failed to initialize interview session.");
      setLoading(false);
    }
  };

  const isEligible = matchData ? matchData.is_eligible !== false : true;

  return (
    <div style={{ maxWidth: "680px", margin: "0 auto" }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
          Configure Interview Session
        </h2>
        <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Review your target selection, role fit analysis, and choose interview duration.
        </p>
      </div>

      <div className="saas-card" style={{ padding: "1.75rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Read-Only Selected Company & Role */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div style={{ padding: "0.85rem 1rem", backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px" }}>
              <span style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
                <Building2 size={13} color="#64748b" /> Target Company
              </span>
              <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b" }}>
                {selectedCompany?.name || (fetchingData ? "Loading..." : "Selected Company")}
              </div>
            </div>

            <div style={{ padding: "0.85rem 1rem", backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px" }}>
              <span style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
                <Briefcase size={13} color="#64748b" /> Target Role
              </span>
              <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b" }}>
                {selectedRole?.title ? `${selectedRole.title}${selectedRole.level ? ` (${selectedRole.level})` : ""}` : (fetchingData ? "Loading..." : "Selected Role")}
              </div>
            </div>
          </div>

          {/* Real Role Fit & Requirements Comparison */}
          {matchData && (
            <div
              style={{
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "10px",
                padding: "1rem 1.15rem"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#09090b" }}>
                  Role Fit Analysis: {matchData.role_title}
                </span>
                <span
                  style={{
                    backgroundColor: matchData.overall_score >= 70 ? "#ecfdf5" : matchData.overall_score > 0 ? "#ede9fe" : "#f4f4f5",
                    color: matchData.overall_score >= 70 ? "#059669" : matchData.overall_score > 0 ? "#6366f1" : "#71717a",
                    border: `1px solid ${matchData.overall_score >= 70 ? "#a7f3d0" : matchData.overall_score > 0 ? "#ddd6fe" : "#e4e4e7"}`,
                    padding: "0.15rem 0.5rem",
                    borderRadius: "6px",
                    fontSize: "0.75rem",
                    fontWeight: 700
                  }}
                >
                  {Math.round(matchData.overall_score)}% Match
                </span>
              </div>

              {matchData.what_you_have && matchData.what_you_have.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap", fontSize: "0.76rem", marginBottom: "0.4rem" }}>
                  <strong style={{ color: "#059669" }}>✓ You have:</strong>
                  {matchData.what_you_have.map((item: string, idx: number) => (
                    <span key={idx} className="badge" style={{ backgroundColor: "#ecfdf5", color: "#059669", border: "1px solid #a7f3d0", fontSize: "0.72rem" }}>
                      {item}
                    </span>
                  ))}
                </div>
              )}

              {matchData.what_you_are_missing && matchData.what_you_are_missing.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap", fontSize: "0.76rem" }}>
                  <strong style={{ color: "#dc2626" }}>✕ Missing:</strong>
                  {matchData.what_you_are_missing.map((item: string, idx: number) => (
                    <span key={idx} className="badge" style={{ backgroundColor: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca", fontSize: "0.72rem" }}>
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Duration */}
          <div>
            <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#52525b", marginBottom: "0.35rem" }}>
              Duration (Minutes)
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
              {[10, 15, 30].map((d) => {
                const selected = duration === d;
                return (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDuration(d)}
                    style={{
                      padding: "0.6rem 0.5rem",
                      borderRadius: "8px",
                      border: `1px solid ${selected ? "#09090b" : "#e4e4e7"}`,
                      backgroundColor: selected ? "#09090b" : "#ffffff",
                      color: selected ? "#ffffff" : "#52525b",
                      fontSize: "0.825rem",
                      fontWeight: selected ? 600 : 500,
                      cursor: "pointer",
                      transition: "all 0.15s ease"
                    }}
                  >
                    {d} Minutes
                  </button>
                );
              })}
            </div>
          </div>

          {/* Eligibility Gate Notice or Start Button */}
          {!isEligible ? (
            <div
              style={{
                backgroundColor: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: "10px",
                padding: "1rem 1.15rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.6rem"
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "#92400e" }}>
                Your profile needs a little more information
              </div>
              <p style={{ fontSize: "0.825rem", color: "#78350f", margin: 0, lineHeight: 1.45 }}>
                To create a meaningful role-specific interview, we need more evidence from your resume. Add a few technical skills, projects, or relevant experience and try again.
              </p>
              <div>
                <a
                  href="/resume"
                  className="btn btn-primary"
                  style={{
                    display: "inline-flex",
                    fontSize: "0.825rem",
                    padding: "0.45rem 1rem",
                    backgroundColor: "#b45309",
                    color: "#ffffff"
                  }}
                >
                  Update Resume / Profile
                </a>
              </div>
            </div>
          ) : (
            <button
              onClick={handleStartInterview}
              disabled={loading || !selectedRoleId || !selectedCompanyId}
              className="btn btn-primary"
              style={{
                width: "100%",
                padding: "0.75rem",
                fontSize: "0.9rem",
                marginTop: "0.5rem",
                justifyContent: "center"
              }}
            >
              <Play size={16} /> <span>{loading ? "Generating Session..." : "Begin Practice Interview"}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ConfigureInterviewPage() {
  return (
    <WorkspaceLayout sectionTitle="Configure Session" sectionSubtitle="Review target selection and launch practice">
      <Suspense fallback={<div className="saas-card skeleton" style={{ height: "400px", maxWidth: "680px", margin: "0 auto" }} />}>
        <ConfigureInterviewContent />
      </Suspense>
    </WorkspaceLayout>
  );
}
