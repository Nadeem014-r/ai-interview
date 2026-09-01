"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { getStoredToken, removeStoredToken } from "@/lib/auth";
import { apiRequest } from "@/lib/api";
import {
  Sparkles,
  LayoutDashboard,
  Mic,
  FileText,
  Building2,
  History,
  Code2,
  Settings,
  Shield,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  User
} from "lucide-react";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
  sectionTitle?: string;
  sectionSubtitle?: string;
  hideHeader?: boolean;
  contentMaxWidth?: string;
}

export const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({
  children,
  sectionTitle,
  sectionSubtitle,
  hideHeader = false,
  contentMaxWidth = "1160px"
}) => {
  const router = useRouter();
  const pathname = usePathname();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userData, setUserData] = useState<{ full_name?: string; email?: string; role?: string } | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (token) {
      apiRequest<{ full_name?: string; email?: string; role?: string }>("/auth/me")
        .then((user) => {
          if (user) setUserData(user);
        })
        .catch(() => {});
    }
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    removeStoredToken();
    router.push("/login");
  };

  const navItems = [
    {
      group: "Workspace",
      items: [
        { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
        { href: "/interview/configure", label: "Interview", icon: Mic },
        { href: "/resume", label: "Resume", icon: FileText },
        { href: "/companies", label: "Companies", icon: Building2 },
        { href: "/history", label: "History", icon: History },
      ]
    },
    {
      group: "Tools",
      items: [
        { href: "/coding", label: "Coding", icon: Code2 },
        { href: "/profile", label: "Settings", icon: Settings },
      ]
    }
  ];

  // Derive section title if not provided
  const getHeaderTitle = () => {
    if (sectionTitle) return sectionTitle;
    if (pathname.startsWith("/dashboard")) return "Overview";
    if (pathname.startsWith("/interview")) return "Interview Workspace";
    if (pathname.startsWith("/resume")) return "Resume Intelligence";
    if (pathname.startsWith("/companies")) return "Target Companies";
    if (pathname.startsWith("/history")) return "Interview History";
    if (pathname.startsWith("/reports")) return "Interview Intelligence";
    if (pathname.startsWith("/profile")) return "Account Settings";
    if (pathname.startsWith("/coding")) return "Coding Sandbox";
    if (pathname.startsWith("/admin")) return "Admin Control Panel";
    return "Workspace";
  };

  const isNavActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  const displayName = userData?.full_name || "Candidate";
  const displayEmail = userData?.email || "student@university.edu";
  const userInitial = displayName.charAt(0).toUpperCase();

  return (
    <div style={{ display: "flex", minHeight: "100vh", backgroundColor: "var(--bg-page)", color: "var(--text-primary)" }}>
      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(9, 9, 11, 0.4)",
            backdropFilter: "blur(4px)",
            WebkitBackdropFilter: "blur(4px)",
            zIndex: 90,
          }}
        />
      )}

      {/* Persistent Left Sidebar */}
      <aside
        style={{
          width: collapsed ? "68px" : "240px",
          backgroundColor: "#ffffff",
          borderRight: "1px solid #e4e4e7",
          display: "flex",
          flexDirection: "column",
          position: "fixed",
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 100,
          transition: "width 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s ease",
          transform: mobileOpen ? "translateX(0)" : undefined,
        }}
        className={mobileOpen ? "sidebar-mobile-open" : "sidebar-desktop"}
      >
        {/* Brand Header */}
        <div
          style={{
            height: "58px",
            borderBottom: "1px solid #f4f4f5",
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "space-between",
            padding: collapsed ? "0" : "0 1rem",
            position: "relative"
          }}
        >
          <Link
            href="/dashboard"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.55rem",
              textDecoration: "none",
              overflow: "hidden"
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                backgroundColor: "#09090b",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                boxShadow: "0 1px 2px rgba(0,0,0,0.08)"
              }}
            >
              <Sparkles size={17} strokeWidth={2.2} />
            </div>
            {!collapsed && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    color: "#09090b",
                    letterSpacing: "-0.025em",
                    lineHeight: 1.1
                  }}
                >
                  OfferScript
                </span>
                <span style={{ fontSize: "0.65rem", color: "#71717a", fontWeight: 500 }}>
                  AI Placement Workspace
                </span>
              </div>
            )}
          </Link>

          {/* Desktop Collapse Toggle */}
          {!collapsed && (
            <button
              onClick={() => setCollapsed(true)}
              style={{
                background: "transparent",
                border: "none",
                color: "#71717a",
                cursor: "pointer",
                padding: "0.25rem",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
              className="desktop-only-btn"
            >
              <ChevronLeft size={16} />
            </button>
          )}
        </div>

        {/* Expand button when collapsed */}
        {collapsed && (
          <div style={{ padding: "0.4rem", display: "flex", justifyContent: "center" }}>
            <button
              onClick={() => setCollapsed(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "#71717a",
                cursor: "pointer",
                padding: "0.3rem",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}

        {/* Navigation Groups */}
        <div style={{ flex: 1, padding: "0.75rem 0.5rem", overflowY: "auto", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {navItems.map((group) => (
            <div key={group.group}>
              {!collapsed && (
                <div
                  style={{
                    fontSize: "0.68rem",
                    fontWeight: 600,
                    color: "#a1a1aa",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    padding: "0 0.65rem 0.4rem"
                  }}
                >
                  {group.group}
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                {group.items.map((item) => {
                  const active = isNavActive(item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.65rem",
                        padding: collapsed ? "0.6rem 0" : "0.5rem 0.65rem",
                        justifyContent: collapsed ? "center" : "flex-start",
                        borderRadius: "8px",
                        fontSize: "0.825rem",
                        fontWeight: active ? 600 : 500,
                        textDecoration: "none",
                        color: active ? "#09090b" : "#52525b",
                        backgroundColor: active ? "var(--accent-brand-light)" : "transparent",
                        transition: "all 0.15s ease"
                      }}
                    >
                      <Icon
                        size={17}
                        color={active ? "var(--accent-brand)" : "#71717a"}
                        strokeWidth={active ? 2.2 : 1.8}
                      />
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Admin link if user is admin or on /admin */}
          {(pathname.startsWith("/admin") || userData?.role === "admin") && (
            <div>
              {!collapsed && (
                <div
                  style={{
                    fontSize: "0.68rem",
                    fontWeight: 600,
                    color: "#a1a1aa",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    padding: "0 0.65rem 0.4rem"
                  }}
                >
                  Admin
                </div>
              )}
              <Link
                href="/admin"
                title={collapsed ? "Admin Control" : undefined}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.65rem",
                  padding: collapsed ? "0.6rem 0" : "0.5rem 0.65rem",
                  justifyContent: collapsed ? "center" : "flex-start",
                  borderRadius: "8px",
                  fontSize: "0.825rem",
                  fontWeight: pathname.startsWith("/admin") ? 600 : 500,
                  textDecoration: "none",
                  color: pathname.startsWith("/admin") ? "#09090b" : "#52525b",
                  backgroundColor: pathname.startsWith("/admin") ? "var(--accent-brand-light)" : "transparent",
                  transition: "all 0.15s ease"
                }}
              >
                <Shield size={17} color={pathname.startsWith("/admin") ? "var(--accent-brand)" : "#71717a"} />
                {!collapsed && <span>Admin Control</span>}
              </Link>
            </div>
          )}
        </div>

        {/* Bottom User Area */}
        <div
          style={{
            borderTop: "1px solid #f4f4f5",
            padding: "0.75rem 0.65rem",
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "space-between",
            gap: "0.5rem"
          }}
        >
          <Link
            href="/profile"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.55rem",
              textDecoration: "none",
              overflow: "hidden",
              flex: 1
            }}
            title={displayName}
          >
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                backgroundColor: "#09090b",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.75rem",
                fontWeight: 700,
                flexShrink: 0
              }}
            >
              {userInitial}
            </div>
            {!collapsed && (
              <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                <span
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "#09090b",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis"
                  }}
                >
                  {displayName}
                </span>
                <span
                  style={{
                    fontSize: "0.68rem",
                    color: "#71717a",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis"
                  }}
                >
                  {displayEmail}
                </span>
              </div>
            )}
          </Link>

          {!collapsed && (
            <button
              onClick={handleLogout}
              style={{
                background: "transparent",
                border: "none",
                color: "#71717a",
                cursor: "pointer",
                padding: "0.35rem",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut size={15} />
            </button>
          )}
        </div>
      </aside>

      {/* Main Workspace Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          marginLeft: collapsed ? "68px" : "240px",
          minWidth: 0,
          transition: "margin-left 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
        }}
        className="workspace-main-container"
      >
        {/* Top Workspace Header Bar */}
        {!hideHeader ? (
          <header
            style={{
              height: "58px",
              backgroundColor: "rgba(255, 255, 255, 0.9)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              borderBottom: "1px solid #e4e4e7",
              padding: "0 1.5rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              position: "sticky",
              top: 0,
              zIndex: 40
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              {/* Mobile Menu Button */}
              <button
                onClick={() => setMobileOpen(!mobileOpen)}
                style={{
                  background: "transparent",
                  border: "1px solid #e4e4e7",
                  borderRadius: "6px",
                  padding: "0.35rem",
                  cursor: "pointer",
                  display: "none"
                }}
                className="mobile-hamburger-btn"
                aria-label="Toggle navigation menu"
              >
                {mobileOpen ? <X size={18} /> : <Menu size={18} />}
              </button>

              <div>
                <h1
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 600,
                    color: "#09090b",
                    margin: 0,
                    letterSpacing: "-0.01em"
                  }}
                >
                  {getHeaderTitle()}
                </h1>
                {sectionSubtitle && (
                  <span style={{ fontSize: "0.72rem", color: "#71717a" }}>{sectionSubtitle}</span>
                )}
              </div>
            </div>

            {/* Top Right Status Badge / Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Link
                href="/interview/configure"
                className="btn btn-primary"
                style={{ padding: "0.35rem 0.75rem", fontSize: "0.78rem" }}
              >
                <Mic size={13} /> <span>New Interview</span>
              </Link>
            </div>
          </header>
        ) : (
          <div className="mobile-header-bar-only" style={{ display: "none", height: "54px", borderBottom: "1px solid #e4e4e7", padding: "0 1rem", alignItems: "center", justifyContent: "space-between", backgroundColor: "#ffffff", position: "sticky", top: 0, zIndex: 40 }}>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              style={{
                background: "transparent",
                border: "1px solid #e4e4e7",
                borderRadius: "6px",
                padding: "0.35rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <div style={{ width: "26px", height: "26px", borderRadius: "6px", backgroundColor: "#09090b", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Sparkles size={14} />
              </div>
              <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "#09090b" }}>OfferScript</span>
            </div>
            <Link
              href="/interview/configure"
              className="btn btn-primary"
              style={{ padding: "0.3rem 0.65rem", fontSize: "0.75rem" }}
            >
              <span>+ New</span>
            </Link>
          </div>
        )}

        {/* Workspace Page Content */}
        <main style={{ flex: 1, padding: hideHeader ? "2rem 2.25rem 4rem" : "1.75rem 1.5rem 4rem", maxWidth: contentMaxWidth, width: "100%", margin: "0 auto" }}>
          {children}
        </main>
      </div>

      <style jsx global>{`
        @media (max-width: 768px) {
          .mobile-header-bar-only {
            display: flex !important;
          }
          .sidebar-desktop {
            transform: translateX(-100%) !important;
          }
          .sidebar-mobile-open {
            transform: translateX(0) !important;
            width: 240px !important;
          }
          .workspace-main-container {
            margin-left: 0 !important;
          }
          .mobile-hamburger-btn {
            display: flex !important;
          }
          .desktop-only-btn {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};
