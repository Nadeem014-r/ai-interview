"use client";

import React from "react";

interface ScoreRadarChartProps {
  scores: Record<string, number>;
}

export const ScoreRadarChart: React.FC<ScoreRadarChartProps> = ({ scores }) => {
  const entries = Object.entries(scores || {});

  if (entries.length === 0) {
    return <p style={{ color: "var(--text-tertiary)", fontSize: "0.825rem", margin: 0 }}>No rubric breakdown data available.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
      {entries.map(([label, rawVal]) => {
        const val = Math.round(Math.max(0, Math.min(10, Number(rawVal) || 0)) * 10) / 10;
        return (
          <div key={label}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.825rem", marginBottom: "0.3rem" }}>
              <span style={{ textTransform: "capitalize", color: "var(--text-secondary)", fontWeight: 500 }}>{label.replace(/_/g, " ")}</span>
              <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{val} <span style={{ color: "var(--text-tertiary)", fontWeight: 400 }}>/ 10</span></span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, val * 10))}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
};
