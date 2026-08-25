"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { removeStoredToken } from "@/lib/auth";
import { Bot, User as UserIcon, LogOut, Shield } from "lucide-react";

export const Navbar: React.FC = () => {
  const router = useRouter();

  const handleLogout = () => {
    removeStoredToken();
    router.push("/login");
  };

  return (
    <nav style={{
      background: "var(--bg-glass)",
      backdropFilter: "blur(16px)",
      borderBottom: "1px solid var(--border-subtle)",
      padding: "0.9rem 2rem",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50
    }}>
      <Link href="/dashboard" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <div style={{
          background: "linear-gradient(135deg, var(--primary), var(--accent-cyan))",
          padding: "0.5rem",
          borderRadius: "var(--radius-md)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <Bot size={24} color="#fff" />
        </div>
        <div>
          <h2 style={{ fontSize: "1.25rem", margin: 0, background: "linear-gradient(90deg, #fff, #a5b4fc)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            AI INTERVIEWER
          </h2>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            University Placement Platform
          </span>
        </div>
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
        <Link href="/companies" className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
          Target Catalog
        </Link>
        <Link href="/resume" className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
          Resume Intelligence
        </Link>
        <Link href="/history" className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
          History
        </Link>
        <Link href="/profile" className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
          <UserIcon size={16} /> Profile
        </Link>
        <Link href="/admin" className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
          <Shield size={16} /> Admin
        </Link>
        <button onClick={handleLogout} className="btn btn-secondary" style={{ padding: "0.5rem 1rem", fontSize: "0.85rem", color: "var(--accent-rose)" }}>
          <LogOut size={16} /> Logout
        </button>
      </div>

    </nav>
  );
};
