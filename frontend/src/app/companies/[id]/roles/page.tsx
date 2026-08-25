"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { Role } from "@/types";
import { Briefcase, CheckCircle2, Play } from "lucide-react";

export default function CompanyRolesPage() {
  const params = useParams();
  const companyId = params.id;
  const [roles, setRoles] = useState<Role[]>([]);

  useEffect(() => {
    async function loadRoles() {
      try {
        const data: any = await apiRequest(`/companies/${companyId}/roles`);
        setRoles(data || []);
      } catch (err) {
        console.error(err);
      }
    }
    if (companyId) loadRoles();
  }, [companyId]);

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />
      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ marginBottom: "2rem" }}>
          <h2>Available Target Roles</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Select a target role to launch an adaptive technical mock interview tailored to this job specification.
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {roles.map((r) => (
            <div key={r.id} className="glass-card" style={{ padding: "1.75rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ maxWidth: "70%" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
                  <Briefcase size={20} color="var(--accent-cyan)" />
                  <h3 style={{ fontSize: "1.2rem" }}>{r.title}</h3>
                  <span className="badge badge-primary">{r.level}</span>
                </div>

                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>{r.description}</p>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                  {r.required_skills.map((s) => (
                    <span key={s} className="badge badge-success">{s}</span>
                  ))}
                </div>
              </div>

              <Link href={`/interview/configure?company_id=${companyId}&role_id=${r.id}`} className="btn btn-primary">
                <Play size={16} /> Select & Configure
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
