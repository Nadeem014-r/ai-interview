"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { Company } from "@/types";
import { Building2, Globe, ChevronRight } from "lucide-react";

export default function CompaniesCatalogPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadCompanies() {
      try {
        const data: any = await apiRequest("/companies");
        setCompanies(data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadCompanies();
  }, []);

  return (
    <WorkspaceLayout sectionTitle="Target Companies" sectionSubtitle="Ground mock interviews in official employer specs">
      <div style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
          Target Company Catalog
        </h2>
        <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Ground interview questioning in official target company culture, tech stacks, and role expectations.
        </p>
      </div>

      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
          <div className="saas-card skeleton" style={{ height: "200px" }} />
          <div className="saas-card skeleton" style={{ height: "200px" }} />
          <div className="saas-card skeleton" style={{ height: "200px" }} />
        </div>
      ) : companies.length === 0 ? (
        <div className="saas-card" style={{ padding: "3rem", textAlign: "center" }}>
          <Building2 size={36} color="#a1a1aa" style={{ marginBottom: "0.5rem" }} />
          <h3 style={{ fontSize: "1rem", color: "#09090b" }}>No companies cataloged yet</h3>
          <p style={{ color: "#71717a", fontSize: "0.85rem" }}>Check back later or configure your target roles directly.</p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(310px, 1fr))", gap: "1rem" }}>
          {companies.map((c) => (
            <div key={c.id} className="saas-card" style={{ padding: "1.35rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <div style={{ backgroundColor: "#f4f4f5", padding: "0.4rem", borderRadius: "8px", border: "1px solid #e4e4e7", color: "#09090b" }}>
                      <Building2 size={18} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: "1.05rem", fontWeight: 600, color: "#09090b", margin: 0 }}>{c.name}</h3>
                      {c.website && (
                        <span style={{ fontSize: "0.75rem", color: "#71717a", display: "flex", alignItems: "center", gap: "0.2rem", marginTop: "0.1rem" }}>
                          <Globe size={11} /> {c.website.replace(/^https?:\/\//, '')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <p style={{ color: "#71717a", fontSize: "0.825rem", marginBottom: "0.85rem", lineHeight: 1.5 }}>
                  {c.description}
                </p>

                {c.culture_keywords && c.culture_keywords.length > 0 && (
                  <div style={{ marginBottom: "1.25rem" }}>
                    <span style={{ fontSize: "0.7rem", color: "#71717a", textTransform: "uppercase", display: "block", marginBottom: "0.3rem", fontWeight: 600 }}>Culture & Tech Keywords</span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
                      {c.culture_keywords.map((k) => (
                        <span key={k} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>{k}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <Link href={`/companies/${c.id}/roles`} className="btn btn-secondary" style={{ width: "100%", justifyContent: "center", fontSize: "0.8rem" }}>
                <span>Explore Roles & Topics</span> <ChevronRight size={14} />
              </Link>
            </div>
          ))}
        </div>
      )}
    </WorkspaceLayout>
  );
}
