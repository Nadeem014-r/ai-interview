"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { Company } from "@/types";
import { Building, Globe, ChevronRight } from "lucide-react";

export default function CompaniesCatalogPage() {
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    async function loadCompanies() {
      try {
        const data: any = await apiRequest("/companies");
        setCompanies(data || []);
      } catch (err) {
        console.error(err);
      }
    }
    loadCompanies();
  }, []);

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />
      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ marginBottom: "2rem" }}>
          <h2>Target Company Catalog</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Ground interview questioning in official target company culture, tech stacks, and role expectations.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
          {companies.map((c) => (
            <div key={c.id} className="glass-card" style={{ padding: "1.75rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <div style={{ background: "rgba(99, 102, 241, 0.15)", padding: "0.5rem", borderRadius: "var(--radius-md)" }}>
                      <Building size={24} color="var(--primary)" />
                    </div>
                    <div>
                      <h3 style={{ fontSize: "1.2rem" }}>{c.name}</h3>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{c.website}</span>
                    </div>
                  </div>
                </div>

                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.25rem", lineHeight: 1.5 }}>
                  {c.description}
                </p>

                <div style={{ marginBottom: "1.5rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "0.4rem" }}>Culture Keywords</span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                    {c.culture_keywords.map((k) => (
                      <span key={k} className="badge badge-primary">{k}</span>
                    ))}
                  </div>
                </div>
              </div>

              <Link href={`/companies/${c.id}/roles`} className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }}>
                Explore Roles & Topics <ChevronRight size={16} />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
