"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setStoredToken } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import { Sparkles, LogIn, AlertCircle, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("student@university.edu");
  const [password, setPassword] = useState("StudentPass123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res: any = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setStoredToken(res.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Invalid credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", backgroundColor: "var(--bg-page)", color: "var(--text-primary)" }}>
      {/* Top Header */}
      <header style={{ padding: "1.25rem 2rem", borderBottom: "1px solid var(--border-subtle)", backgroundColor: "var(--bg-surface)" }}>
        <Link href="/" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.55rem" }}>
          <div
            style={{
              backgroundColor: "#6d5cff",
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
          <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
            OfferScript
          </span>
        </Link>
      </header>

      {/* Main Form Box */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem 1.5rem" }}>
        <div className="saas-card" style={{ width: "100%", maxWidth: "390px", padding: "2.25rem 2rem" }}>
          <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
            <h1 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.03em" }}>Welcome back</h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
              Sign in to your OfferScript workspace
            </p>
          </div>

          {error && (
            <div style={{ padding: "0.65rem 0.85rem", backgroundColor: "var(--accent-rose-light)", border: "1px solid rgba(251, 113, 133, 0.32)", borderRadius: "8px", color: "var(--accent-rose)", fontSize: "0.825rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <AlertCircle size={15} /> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem" }}>Email Address</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="form-input" placeholder="student@university.edu" />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem" }}>Password</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="form-input" placeholder="••••••••" />
            </div>

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: "100%", marginTop: "0.5rem", padding: "0.65rem" }}>
              <LogIn size={15} /> <span>{loading ? "Signing in..." : "Sign In to Workspace"}</span>
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "1.5rem", fontSize: "0.825rem", color: "var(--text-muted)" }}>
            Don't have an account? <Link href="/register" style={{ color: "var(--text-primary)", textDecoration: "none", fontWeight: 600 }}>Create account</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
