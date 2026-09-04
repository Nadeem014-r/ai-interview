"use client";

import React from "react";

export const Card: React.FC<{ children: React.ReactNode; className?: string; style?: React.CSSProperties }> = ({ children, className = "", style }) => (
  <div className={`saas-card ${className}`} style={{ padding: "1.5rem", ...style }}>
    {children}
  </div>
);

export const Alert: React.FC<{ type?: "info" | "warning" | "danger" | "success"; children: React.ReactNode }> = ({ type = "info", children }) => {
  const styles = {
    info: { bg: "var(--accent-brand-light)", border: "#c7d2fe", color: "var(--accent-brand)" },
    warning: { bg: "var(--accent-amber-light)", border: "#fde68a", color: "var(--accent-amber)" },
    danger: { bg: "var(--accent-rose-light)", border: "#fecdd3", color: "var(--accent-rose)" },
    success: { bg: "var(--accent-emerald-light)", border: "#a7f3d0", color: "var(--accent-emerald)" }
  };
  const current = styles[type] || styles.info;
  return (
    <div style={{
      padding: "0.75rem 1rem",
      backgroundColor: current.bg,
      border: `1px solid ${current.border}`,
      borderRadius: "var(--radius-md)",
      color: current.color,
      fontSize: "0.875rem",
      marginBottom: "1rem"
    }}>
      {children}
    </div>
  );
};
