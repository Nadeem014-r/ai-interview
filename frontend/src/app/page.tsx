"use client";

import React from "react";
import Link from "next/link";
import { Bot, Cpu, FileCheck, ShieldCheck, Sparkles, ArrowRight } from "lucide-react";

export default function LandingPage() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Navbar */}
      <header style={{ padding: "1.5rem 3rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ background: "linear-gradient(135deg, var(--primary), var(--accent-cyan))", padding: "0.5rem", borderRadius: "var(--radius-md)" }}>
            <Bot size={28} color="#fff" />
          </div>
          <h2 style={{ fontSize: "1.4rem", background: "linear-gradient(90deg, #fff, #a5b4fc)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            AI INTERVIEWER
          </h2>
        </div>
        <div style={{ display: "flex", gap: "1rem" }}>
          <Link href="/login" className="btn btn-secondary">Login</Link>
          <Link href="/register" className="btn btn-primary">Register Free</Link>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "4rem 2rem" }}>
        <div className="badge badge-primary" style={{ marginBottom: "1.5rem" }}>
          <Sparkles size={14} style={{ marginRight: "0.4rem" }} /> University Ready Placement System
        </div>
        <h1 style={{ fontSize: "3.5rem", maxWidth: "900px", lineHeight: 1.15, marginBottom: "1.5rem" }}>
          Adaptive AI Technical Interviewer & Candidate Performance Evaluator
        </h1>
        <p style={{ fontSize: "1.2rem", color: "var(--text-secondary)", maxWidth: "700px", marginBottom: "2.5rem" }}>
          Prepare for top technology placement drives with real-time adaptive questioning, RAG company-grounded intelligence, multi-dimensional rubric scoring, and authoritative progress reports.
        </p>

        <div style={{ display: "flex", gap: "1.25rem" }}>
          <Link href="/register" className="btn btn-primary" style={{ padding: "1rem 2rem", fontSize: "1.1rem" }}>
            Start Mock Interview <ArrowRight size={20} />
          </Link>
          <Link href="/login" className="btn btn-secondary" style={{ padding: "1rem 2rem", fontSize: "1.1rem" }}>
            Placement Officer Portal
          </Link>
        </div>
      </section>

      {/* Feature Grid */}
      <section style={{ padding: "4rem 3rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.5rem", maxWidth: "1200px", margin: "0 auto 4rem", width: "100%" }}>
        <div className="glass-card">
          <FileCheck size={32} color="var(--accent-cyan)" style={{ marginBottom: "1rem" }} />
          <h3>Resume Intelligence</h3>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem", fontSize: "0.9rem" }}>
            Structured parsing that strictly separates explicit resume facts from model-inferred candidate seniority.
          </p>
        </div>

        <div className="glass-card">
          <Cpu size={32} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3>Adaptive Interview Engine</h3>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem", fontSize: "0.9rem" }}>
            Deterministic backend state machine regulating dynamic difficulty transitions based on response quality.
          </p>
        </div>

        <div className="glass-card">
          <ShieldCheck size={32} color="var(--accent-emerald)" style={{ marginBottom: "1rem" }} />
          <h3>RAG Company Grounding</h3>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem", fontSize: "0.9rem" }}>
            Vector similarity retrieval from official job specs ensuring grounded, non-hallucinated question sets.
          </p>
        </div>
      </section>
    </div>
  );
}
