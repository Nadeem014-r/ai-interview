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
  Building2
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
    { href: "/companies", label: "Companies", icon: Building2 },
    { href: "/history", label: "History", icon: HistoryIcon },
    { href: "/profile", label: "Profile", icon: UserIcon },
  ];

  return (
    <nav style={{
      backgroundColor: "rgba(255, 255, 255, 0.92)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      borderBottom: "1px solid #e4e4e7",
      padding: "0.65rem 1.5rem",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50,
      flexWrap: "wrap",
      gap: "0.75rem"
    }}>
      {/* Left: Brand Identity */}
      <Link href="/dashboard" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <div style={{
          backgroundColor: "#09090b",
          width: "32px",
          height: "32px",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#ffffff",
          boxShadow: "0 1px 2px rgba(0,0,0,0.08)"
        }}>
          <Bot size={18} strokeWidth={2.2} />
        </div>
        <div>
          <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em" }}>
            AI INTERVIEWER
          </span>
          <span style={{ display: "block", fontSize: "0.68rem", color: "#71717a", fontWeight: 500, letterSpacing: "0.01em" }}>
            Placement Platform
          </span>
        </div>
      </Link>

      {/* Right: Nav Links + User Avatar + Logout Button */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap" }}>
        {navLinks.map((link) => {
          const isActive = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.65rem",
                borderRadius: "6px",
                fontSize: "0.825rem",
                fontWeight: isActive ? 600 : 500,
                textDecoration: "none",
                color: isActive ? "#09090b" : "#52525b",
                backgroundColor: isActive ? "#f4f4f5" : "transparent",
                transition: "all 0.15s ease"
              }}
            >
              <Icon size={15} color={isActive ? "#09090b" : "#71717a"} strokeWidth={isActive ? 2.2 : 1.8} />
              <span>{link.label}</span>
            </Link>
          );
        })}

        {userName && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            padding: "0.25rem 0.55rem 0.25rem 0.35rem",
            backgroundColor: "#f4f4f5",
            borderRadius: "9999px",
            border: "1px solid #e4e4e7",
            fontSize: "0.78rem",
            color: "#27272a",
            marginLeft: "0.4rem"
          }}>
            <div style={{
              width: "20px",
              height: "20px",
              borderRadius: "50%",
              backgroundColor: "#09090b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: "0.68rem",
              fontWeight: 700
            }}>
              {userName.charAt(0).toUpperCase()}
            </div>
            <span style={{ fontWeight: 600 }}>{userName.split(" ")[0]}</span>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="btn btn-secondary"
          style={{ padding: "0.35rem 0.65rem", fontSize: "0.78rem", marginLeft: "0.25rem", color: "#71717a" }}
          aria-label="Logout"
          title="Sign out of your account"
        >
          <LogOut size={14} />
          <span>Logout</span>
        </button>
      </div>
    </nav>
  );
};
