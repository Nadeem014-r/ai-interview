"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { removeStoredToken, getStoredToken } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import {
  Bot,
  User as UserIcon,
  LogOut,
  LayoutDashboard,
  FileText,
  History as HistoryIcon,
  Sparkles
} from "lucide-react";

export const Navbar: React.FC = () => {
  const router = useRouter();
  const pathname = usePathname();
  const [userName, setUserName] = useState<string>("");

  useEffect(() => {
    const token = getStoredToken();
    if (token) {
      apiRequest<{ full_name?: string; email?: string }>("/auth/me")
        .then((user) => {
          if (user && user.full_name) {
            setUserName(user.full_name);
          }
        })
        .catch(() => {});
    }
  }, []);

  const handleLogout = () => {
    removeStoredToken();
    router.push("/login");
  };

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/resume", label: "Resume", icon: FileText },
    { href: "/companies", label: "Companies", icon: Sparkles },
    { href: "/history", label: "History", icon: HistoryIcon },
    { href: "/profile", label: "Profile", icon: UserIcon },
  ];

  return (
    <nav style={{
      backgroundColor: "#ffffff",
      borderBottom: "1px solid #e2e8f0",
      boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.04)",
      padding: "0.75rem 2rem",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50,
      flexWrap: "wrap",
      gap: "1rem"
    }}>
      {/* Left: Premium Logo */}
      <Link href="/dashboard" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.65rem" }}>
        <div style={{
          backgroundColor: "#4f46e5",
          width: "34px",
          height: "34px",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#ffffff"
        }}>
          <Bot size={20} />
        </div>
        <div>
          <span style={{ fontSize: "1.1rem", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.03em" }}>
            AI INTERVIEWER
          </span>
          <span style={{ display: "block", fontSize: "0.68rem", color: "#64748b", fontWeight: 500, letterSpacing: "0.02em" }}>
            Placement Platform
          </span>
        </div>
      </Link>

      {/* Right: Nav Links + User Avatar + Outlined Logout Button */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.45rem 0.75rem",
                borderRadius: "8px",
                fontSize: "0.88rem",
                fontWeight: isActive ? 600 : 500,
                textDecoration: "none",
                color: isActive ? "#4f46e5" : "#475569",
                backgroundColor: isActive ? "#eef2ff" : "transparent",
                transition: "all 0.15s ease"
              }}
            >
              <Icon size={16} color={isActive ? "#4f46e5" : "#64748b"} />
              <span>{link.label}</span>
            </Link>
          );
        })}

        {userName && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.45rem",
            padding: "0.35rem 0.7rem",
            backgroundColor: "#f8fafc",
            borderRadius: "9999px",
            border: "1px solid #e2e8f0",
            fontSize: "0.82rem",
            color: "#334155",
            marginLeft: "0.5rem"
          }}>
            <div style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              backgroundColor: "#4f46e5",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: "0.72rem",
              fontWeight: 700
            }}>
              {userName.charAt(0).toUpperCase()}
            </div>
            <span style={{ fontWeight: 600 }}>{userName.split(" ")[0]}</span>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="btn btn-outline-danger"
          style={{ padding: "0.45rem 0.85rem", fontSize: "0.85rem", marginLeft: "0.3rem" }}
          aria-label="Logout"
        >
          <LogOut size={15} />
          <span>Logout</span>
        </button>
      </div>
    </nav>
  );
};
