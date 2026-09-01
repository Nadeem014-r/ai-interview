"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setStoredToken } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import { Sparkles, UserPlus, AlertCircle, ArrowRight } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res: any = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({ full_name: fullName, email, password }),
      });
      setStoredToken(res.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "var(--bg-page)", color: "var(--text-primary)" }}>
      {/* Top Header */}
      <header style={{ padding: "1.25rem 2rem", borderBottom: "1px solid #e4e4e7", backgroundColor: "#ffffff" }}>
        <Link href="/" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.55rem" }}>
          <div
            style={{
              backgroundColor: "#09090b",
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff"
            }}
          >
            <Sparkles size={15} />
          </div>
          <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em" }}>
            OfferScript
          </span>
        </Link>
      </header>

      {/* Main Form Box */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem 1.5rem" }}>
        <div className="saas-card" style={{ width: "100%", maxWidth: "410px", padding: "2.25rem 2rem" }}>
          <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
            <h1 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.03em" }}>Build your interview advantage</h1>
            <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.25rem" }}>
              Create your OfferScript candidate workspace
            </p>
          </div>

          {error && (
            <div style={{ padding: "0.65rem 0.85rem", backgroundColor: "var(--accent-rose-light)", border: "1px solid #fecdd3", borderRadius: "8px", color: "var(--accent-rose)", fontSize: "0.825rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <AlertCircle size={15} /> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#52525b", marginBottom: "0.35rem" }}>Full Name</label>
              <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} className="form-input" placeholder="Alex Mercer" />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#52525b", marginBottom: "0.35rem" }}>University / Institutional Email</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="form-input" placeholder="student@university.edu" />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#52525b", marginBottom: "0.35rem" }}>Password</label>
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="form-input" placeholder="Minimum 8 characters" />
            </div>

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: "100%", marginTop: "0.5rem", padding: "0.65rem" }}>
              <UserPlus size={15} /> <span>{loading ? "Creating workspace..." : "Create Free Workspace"}</span>
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.825rem", color: "#71717a" }}>
            Already have an account? <Link href="/login" style={{ color: "#09090b", textDecoration: "none", fontWeight: 600 }}>Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
