"use client";

import React, { useState } from "react";
import { Play, CheckCircle2, AlertCircle } from "lucide-react";

interface MonacoCodingRoomProps {
  onCodeSubmit: (code: string) => void;
}

export const MonacoCodingRoom: React.FC<MonacoCodingRoomProps> = ({ onCodeSubmit }) => {
  const [code, setCode] = useState<string>(`def solve_problem(nums, target):\n    # Implement your optimal O(N) solution here using hash map\n    seen = {}\n    for idx, val in enumerate(nums):\n        diff = target - val\n        if diff in seen:\n            return [seen[diff], idx]\n        seen[val] = idx\n    return []\n`);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [isExecuting, setIsExecuting] = useState(false);

  const handleRunCode = async () => {
    setIsExecuting(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/coding/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: "python", code }),
      });
      const data = await res.json();
      setExecutionResult(data);
    } catch (err) {
      setExecutionResult({ status: "error", stdout: "Execution sandbox connection error." });
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h4 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          💻 Code Editor Sandbox (Isolated Execution)
        </h4>
        <button onClick={handleRunCode} className="btn btn-primary" style={{ padding: "0.4rem 1rem", fontSize: "0.85rem" }}>
          <Play size={16} /> {isExecuting ? "Executing..." : "Run Test Cases"}
        </button>
      </div>

      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={10}
        style={{
          width: "100%",
          fontFamily: "monospace",
          fontSize: "0.9rem",
          background: "#0d1117",
          color: "#e6edf3",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "1rem",
          outline: "none"
        }}
      />

      {executionResult && (
        <div style={{ marginTop: "1rem", padding: "1rem", background: "rgba(0,0,0,0.5)", borderRadius: "var(--radius-md)", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: executionResult.status === "success" ? "#6ee7b7" : "#fda4af" }}>
            {executionResult.status === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <strong>{executionResult.status === "success" ? "Execution Output" : "Execution Error"}</strong>
          </div>
          <pre style={{ marginTop: "0.5rem", fontFamily: "monospace", color: "var(--text-secondary)" }}>
            {executionResult.stdout}
          </pre>
        </div>
      )}
    </div>
  );
};
