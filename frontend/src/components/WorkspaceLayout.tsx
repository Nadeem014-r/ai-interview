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
  /**
   * A timed interview is on screen. Sidebar destinations are shown but not
   * navigable, so a candidate cannot wander off mid-session into, say, the
   * standalone Coding practice tool and lose the interview they are sitting.
   * Sign out stays available -- this is a guard rail, not a trap.
   */
  lockNavigation?: boolean;
}

export const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({
  children,
  sectionTitle,
  sectionSubtitle,
  hideHeader = false,
  contentMaxWidth = "1160px",
  lockNavigation = false
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
    if (pathname.startsWith("/coding")) return "Coding Practice";
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
    <div style={{ display: "flex", minHeight: "100vh", backgroundColor: "transparent", color: "var(--text-primary)" }}>
      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(4, 5, 11, 0.62)",
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
          background: "linear-gradient(180deg, rgba(17, 19, 40, 0.92) 0%, rgba(10, 12, 26, 0.94) 100%)",
          backdropFilter: "blur(20px) saturate(140%)",
          WebkitBackdropFilter: "blur(20px) saturate(140%)",
          borderRight: "1px solid var(--border-subtle)",
          boxShadow: "1px 0 0 rgba(255, 255, 255, 0.04), 18px 0 48px -30px rgba(0, 0, 0, 0.9)",
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
            borderBottom: "1px solid var(--border-subtle)",
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
                background: "linear-gradient(135deg, #6d5cff 0%, #a855f7 100%)",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                boxShadow: "0 6px 18px -6px rgba(124, 92, 255, 0.85), 0 1px 0 rgba(255, 255, 255, 0.25) inset"
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
                    color: "var(--text-primary)",
                    letterSpacing: "-0.025em",
                    lineHeight: 1.1
                  }}
                >
                  OfferScript
                </span>
                <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontWeight: 500 }}>
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
                color: "var(--text-muted)",
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
                color: "var(--text-muted)",
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
                    color: "var(--text-tertiary)",
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
                  // During an interview the same row is rendered as plain text:
                  // identical layout, but nothing to click.
                  const Row: any = lockNavigation ? "div" : Link;
                  return (
                    <Row
                      key={item.href}
                      {...(lockNavigation ? { "aria-disabled": true } : { href: item.href })}
                      title={
                        lockNavigation
                          ? "Unavailable while an interview is in progress"
                          : collapsed
                          ? item.label
                          : undefined
                      }
                      style={{
                        cursor: lockNavigation ? "not-allowed" : "pointer",
                        opacity: lockNavigation && !active ? 0.45 : 1,
                        display: "flex",
                        alignItems: "center",
                        gap: "0.65rem",
                        padding: collapsed ? "0.6rem 0" : "0.5rem 0.65rem",
                        justifyContent: collapsed ? "center" : "flex-start",
                        borderRadius: "8px",
                        fontSize: "0.825rem",
                        fontWeight: active ? 600 : 500,
                        textDecoration: "none",
                        color: active ? "#ffffff" : "var(--text-secondary)",
                        background: active
                          ? "linear-gradient(100deg, rgba(124, 92, 255, 0.32) 0%, rgba(124, 92, 255, 0.10) 100%)"
                          : "transparent",
                        border: `1px solid ${active ? "rgba(139, 125, 255, 0.34)" : "transparent"}`,
                        boxShadow: active ? "0 6px 20px -10px rgba(124, 92, 255, 0.9)" : "none",
                        transition: "all 0.15s ease"
                      }}
                    >
                      <Icon
                        size={17}
                        color={active ? "var(--accent-brand)" : "var(--text-muted)"}
                        strokeWidth={active ? 2.2 : 1.8}
                      />
                      {!collapsed && <span>{item.label}</span>}
                    </Row>
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
                    color: "var(--text-tertiary)",
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
                  color: pathname.startsWith("/admin") ? "#ffffff" : "var(--text-secondary)",
                  background: pathname.startsWith("/admin")
                    ? "linear-gradient(100deg, rgba(124, 92, 255, 0.32) 0%, rgba(124, 92, 255, 0.10) 100%)"
                    : "transparent",
                  border: `1px solid ${pathname.startsWith("/admin") ? "rgba(139, 125, 255, 0.34)" : "transparent"}`,
                  transition: "all 0.15s ease"
                }}
              >
                <Shield size={17} color={pathname.startsWith("/admin") ? "var(--accent-brand)" : "var(--text-muted)"} />
                {!collapsed && <span>Admin Control</span>}
              </Link>
            </div>
          )}
        </div>

        {/* Bottom User Area */}
        <div
          style={{
            borderTop: "1px solid var(--border-subtle)",
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
                background: "linear-gradient(135deg, #6d5cff 0%, #a855f7 100%)",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 4px 14px -4px rgba(124, 92, 255, 0.8)",
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
                    color: "var(--text-primary)",
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
                    color: "var(--text-muted)",
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
                color: "var(--text-muted)",
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
              backgroundColor: "rgba(8, 10, 22, 0.72)",
              backdropFilter: "blur(18px) saturate(140%)",
              WebkitBackdropFilter: "blur(18px) saturate(140%)",
              borderBottom: "1px solid var(--border-subtle)",
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
                  border: "1px solid var(--border-subtle)",
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
                    color: "var(--text-primary)",
                    margin: 0,
                    letterSpacing: "-0.01em"
                  }}
                >
                  {getHeaderTitle()}
                </h1>
                {sectionSubtitle && (
                  <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{sectionSubtitle}</span>
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
          <div className="mobile-header-bar-only" style={{ display: "none", height: "54px", borderBottom: "1px solid var(--border-subtle)", padding: "0 1rem", alignItems: "center", justifyContent: "space-between", backgroundColor: "rgba(8, 10, 22, 0.82)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)", position: "sticky", top: 0, zIndex: 40 }}>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              style={{
                background: "transparent",
                border: "1px solid var(--border-subtle)",
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
              <div style={{ width: "26px", height: "26px", borderRadius: "6px", background: "linear-gradient(135deg, #6d5cff 0%, #a855f7 100%)", color: "#ffffff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Sparkles size={14} />
              </div>
              <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text-primary)" }}>OfferScript</span>
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
