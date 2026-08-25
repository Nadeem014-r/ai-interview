"use client";

import React from "react";

export const Card: React.FC<{ children: React.ReactNode; className?: string; style?: React.CSSProperties }> = ({ children, className = "", style }) => (
  <div className={`glass-card ${className}`} style={{ padding: "1.5rem", ...style }}>
    {children}
  </div>
);

export const Alert: React.FC<{ type?: "info" | "warning" | "danger" | "success"; children: React.ReactNode }> = ({ type = "info", children }) => {
  const colors = {
    info: { bg: "rgba(99, 102, 241, 0.12)", border: "rgba(99, 102, 241, 0.3)", color: "#a5b4fc" },
    warning: { bg: "rgba(245, 158, 11, 0.12)", border: "rgba(245, 158, 11, 0.3)", color: "#fcd34d" },
    danger: { bg: "rgba(244, 63, 94, 0.12)", border: "rgba(244, 63, 94, 0.3)", color: "#fda4af" },
    success: { bg: "rgba(16, 185, 129, 0.12)", border: "rgba(16, 185, 129, 0.3)", color: "#6ee7b7" }
  };
  return (
    <div style={{
      padding: "1rem 1.2rem",
      background: colors[type].bg,
      border: `1px solid ${colors[type].border}`,
      borderRadius: "var(--radius-md)",
      color: colors[type].color,
      fontSize: "0.9rem",
      marginBottom: "1rem"
    }}>
      {children}
    </div>
  );
};
