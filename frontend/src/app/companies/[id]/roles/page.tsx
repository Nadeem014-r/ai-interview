"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { Role, JobMatchResult } from "@/types";
import { Briefcase, ArrowLeft, Play, CheckCircle2, XCircle, AlertCircle, Upload } from "lucide-react";

export default function CompanyRolesPage() {
  const params = useParams();
  const companyId = params.id;
  const [roles, setRoles] = useState<Role[]>([]);
  const [matches, setMatches] = useState<Record<number, JobMatchResult>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadRolesAndMatches() {
      try {
        const [rolesData, matchesData]: [any, any] = await Promise.all([
          apiRequest(`/companies/${companyId}/roles`).catch(() => []),
          apiRequest("/jobs/matches").catch(() => [])
        ]);

        setRoles(rolesData || []);

        const matchMap: Record<number, JobMatchResult> = {};
        if (Array.isArray(matchesData)) {
          matchesData.forEach((m: JobMatchResult) => {
            matchMap[m.role_id] = m;
          });
        }
        setMatches(matchMap);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    if (companyId) loadRolesAndMatches();
  }, [companyId]);

  return (
    <WorkspaceLayout sectionTitle="Target Roles" sectionSubtitle="Role requirements and interview preparation">
      <div style={{ marginBottom: "1.5rem" }}>
        <Link href="/companies" style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", color: "var(--text-muted)", textDecoration: "none", fontSize: "0.825rem", fontWeight: 500, marginBottom: "0.5rem" }}>
          <ArrowLeft size={14} /> Back to Companies
        </Link>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>Available Target Roles</h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Compare real company requirements against your resume evidence and launch role-tailored technical practice.
        </p>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="saas-card skeleton" style={{ height: "120px" }} />
          <div className="saas-card skeleton" style={{ height: "120px" }} />
        </div>
      ) : roles.length === 0 ? (
        <div className="saas-card" style={{ padding: "3rem", textAlign: "center" }}>
          <Briefcase size={36} color="var(--text-tertiary)" style={{ marginBottom: "0.5rem" }} />
          <h3 style={{ fontSize: "1rem", color: "var(--text-primary)" }}>No specific roles listed</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>You can configure a custom mock interview from the configuration page.</p>
          <Link href="/interview/configure" className="btn btn-primary" style={{ marginTop: "1rem" }}>
            Configure Custom Session
          </Link>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          {roles.map((r) => {
            const match = matches[r.id];
            const matchScore = match ? Math.round(match.overall_score) : null;
            const isEligible = match ? match.is_eligible !== false : true;

            return (
              <div key={r.id} className="saas-card" style={{ padding: "1.35rem 1.5rem", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
                <div style={{ maxWidth: "660px", flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem", flexWrap: "wrap" }}>
                    <h3 style={{ fontSize: "1.05rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>{r.title}</h3>
                    <span className="badge badge-neutral" style={{ textTransform: "capitalize" }}>{r.level}</span>
                    {matchScore !== null && (
                      <span
                        className="badge"
                        style={{
                          backgroundColor: matchScore >= 70 ? "var(--accent-emerald-light)" : matchScore > 0 ? "var(--accent-brand-light)" : "var(--bg-subtle)",
                          color: matchScore >= 70 ? "var(--accent-emerald)" : matchScore > 0 ? "var(--accent-brand)" : "var(--text-muted)",
                          border: `1px solid ${matchScore >= 70 ? "rgba(52, 211, 153, 0.32)" : matchScore > 0 ? "rgba(139, 125, 255, 0.28)" : "var(--border-subtle)"}`,
                          fontWeight: 700
                        }}
                      >
                        {matchScore}% Role Match
                      </span>
                    )}
                  </div>

                  <p style={{ color: "var(--text-muted)", fontSize: "0.825rem", marginBottom: "0.75rem", lineHeight: 1.5 }}>{r.description}</p>

                  {/* Real Matched vs Missing Requirements Comparison */}
                  {match && (match.matched_skills.length > 0 || match.missing_skills.length > 0) ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "0.5rem" }}>
                      {match.what_you_have && match.what_you_have.length > 0 && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap", fontSize: "0.76rem" }}>
                          <span style={{ color: "var(--accent-emerald)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "2px" }}>
                            <CheckCircle2 size={12} /> You have:
                          </span>
                          {match.what_you_have.map((s, idx) => (
                            <span key={idx} className="badge" style={{ backgroundColor: "var(--accent-emerald-light)", color: "var(--accent-emerald)", border: "1px solid rgba(52, 211, 153, 0.32)", fontSize: "0.72rem" }}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}

                      {match.what_you_are_missing && match.what_you_are_missing.length > 0 && (
                        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap", fontSize: "0.76rem" }}>
                          <span style={{ color: "var(--accent-rose)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "2px" }}>
                            <XCircle size={12} /> Missing:
                          </span>
                          {match.what_you_are_missing.map((s, idx) => (
                            <span key={idx} className="badge" style={{ backgroundColor: "var(--accent-rose-light)", color: "var(--accent-rose)", border: "1px solid rgba(251, 113, 133, 0.32)", fontSize: "0.72rem" }}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                      {r.required_skills.map((s) => (
                        <span key={s} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>{s}</span>
                      ))}
                    </div>
                  )}

                  {!isEligible && (
                    <div style={{ marginTop: "0.75rem", padding: "0.5rem 0.75rem", backgroundColor: "var(--accent-amber-light)", border: "1px solid rgba(251, 191, 36, 0.32)", borderRadius: "8px", color: "var(--accent-amber)", fontSize: "0.76rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <AlertCircle size={13} />
                      <span>Insufficient resume evidence to generate technical questions for this role.</span>
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.5rem" }}>
                  {isEligible ? (
                    <Link href={`/interview/configure?company_id=${companyId}&role_id=${r.id}`} className="btn btn-primary" style={{ fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                      <Play size={13} /> <span>Select & Configure</span>
                    </Link>
                  ) : (
                    <Link href="/resume" className="btn btn-secondary" style={{ fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                      <Upload size={13} /> <span>Update Resume</span>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </WorkspaceLayout>
  );
}
