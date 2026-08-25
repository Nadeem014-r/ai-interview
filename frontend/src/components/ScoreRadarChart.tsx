"use client";

import React from "react";

interface ScoreRadarChartProps {
  scores: Record<string, number>;
}

export const ScoreRadarChart: React.FC<ScoreRadarChartProps> = ({ scores }) => {
  const entries = Object.entries(scores || {});

  return (
    <div className="glass-card" style={{ padding: "1.5rem" }}>
      <h3 style={{ marginBottom: "1.25rem", fontSize: "1.1rem" }}>Skill & Rubric Score Breakdown</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {entries.map(([label, val]) => (
          <div key={label}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.4rem" }}>
              <span style={{ textTransform: "capitalize", color: "var(--text-secondary)" }}>{label}</span>
              <span style={{ fontWeight: 700, color: "var(--accent-cyan)" }}>{val} / 10</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, val * 10))}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
