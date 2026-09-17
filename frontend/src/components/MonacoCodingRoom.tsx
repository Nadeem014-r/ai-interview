"use client";

import React, { useState } from "react";
import { Code2, Send, Loader2, Lock, Info } from "lucide-react";

/**
 * In-interview coding workspace.
 *
 * There is deliberately no "Run" button. The repository has no isolated
 * execution environment -- /coding/execute used to answer with a canned "all
 * test cases passed" string and now refuses outright -- so a Run button
 * here would either report a fabricated result or require executing a
 * candidate's C++/Java inside the application container. Neither is acceptable,
 * so the workspace collects the solution and the final report grades it by
 * reading it. The candidate is told this up front rather than left to discover
 * it.
 *
 * The submission is final: it goes through the same answer endpoint as every
 * other turn, whose per-question idempotency means a retry or a refresh replays
 * the stored turn instead of creating a second submission.
 */

type Language = "cpp" | "java";

const STARTERS: Record<Language, string> = {
  cpp: `#include <bits/stdc++.h>
using namespace std;

// Approach:
// Complexity: time O(?), space O(?)

int main() {
    return 0;
}
`,
  java: `import java.util.*;

public class Solution {
    // Approach:
    // Complexity: time O(?), space O(?)

    public static void main(String[] args) {
    }
}
`,
};

const LANGUAGE_LABELS: Record<Language, string> = { cpp: "C++", java: "Java" };

interface MonacoCodingRoomProps {
  questionText: string;
  expectedConcepts?: string[];
  /**
   * Resolves when the submission has been accepted by the interview engine.
   * Not used, and not required, in practice mode: there is nothing to submit to.
   */
  onCodeSubmit?: (submission: string) => Promise<void> | void;
  submitting?: boolean;
  /** True once this turn's submission is on record. */
  submitted?: boolean;
  /**
   * Standalone practice outside any interview. The editor is identical, but
   * there is no submission: no interview turn exists to attach one to, nothing
   * is stored and nothing is graded. The workspace says so and offers no submit
   * control, rather than showing a "Submit solution" button that claimed the
   * final report would read the code.
   */
  practice?: boolean;
}

export const MonacoCodingRoom: React.FC<MonacoCodingRoomProps> = ({
  questionText,
  expectedConcepts = [],
  onCodeSubmit,
  submitting = false,
  submitted = false,
  practice = false,
}) => {
  const [language, setLanguage] = useState<Language>("cpp");
  const [code, setCode] = useState<string>(STARTERS.cpp);
  const [touched, setTouched] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const locked = !practice && (submitted || submitting);

  const switchLanguage = (next: Language) => {
    if (locked) return;
    setLanguage(next);
    // Only replace the buffer while it is still the untouched starter, so a
    // mis-click on the language toggle cannot destroy written work.
    if (!touched) setCode(STARTERS[next]);
  };

  const handleSubmit = async () => {
    if (practice || !onCodeSubmit || locked || !code.trim()) return;
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    await onCodeSubmit(`Language: ${LANGUAGE_LABELS[language]}\n\n${code}`);
  };

  return (
    <div className="saas-card" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ backgroundColor: "#6d5cff", padding: "0.35rem", borderRadius: "6px", color: "#ffffff" }}>
            <Code2 size={15} />
          </div>
          <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--text-primary)" }}>
            {practice ? "Practice Exercise" : "Coding Exercise"}
          </span>
        </div>

        <div style={{ display: "flex", gap: "0.35rem" }} role="group" aria-label="Language">
          {(Object.keys(LANGUAGE_LABELS) as Language[]).map((lang) => (
            <button
              key={lang}
              onClick={() => switchLanguage(lang)}
              disabled={locked}
              aria-pressed={language === lang}
              style={{
                padding: "0.35rem 0.9rem",
                fontSize: "0.8rem",
                fontWeight: 600,
                borderRadius: "8px",
                cursor: locked ? "not-allowed" : "pointer",
                border: `1px solid ${language === lang ? "rgba(139, 125, 255, 0.45)" : "var(--border-subtle)"}`,
                backgroundColor: language === lang ? "var(--accent-brand-light)" : "rgba(255, 255, 255, 0.04)",
                color: language === lang ? "var(--accent-brand-hover)" : "var(--text-secondary)",
              }}
            >
              {LANGUAGE_LABELS[lang]}
            </button>
          ))}
        </div>
      </div>

      <p style={{ fontSize: "1.02rem", fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.55, whiteSpace: "pre-wrap", margin: "0 0 1rem" }}>
        {questionText}
      </p>

      {expectedConcepts.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", alignItems: "center", marginBottom: "1rem" }}>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>Focus:</span>
          {expectedConcepts.map((c) => (
            <span key={c} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>
              {c}
            </span>
          ))}
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "0.5rem",
          padding: "0.65rem 0.85rem",
          marginBottom: "0.85rem",
          borderRadius: "8px",
          backgroundColor: "var(--accent-brand-light)",
          border: "1px solid rgba(139, 125, 255, 0.28)",
          color: "var(--accent-brand-hover)",
          fontSize: "0.78rem",
          lineHeight: 1.45,
        }}
      >
        <Info size={15} style={{ flexShrink: 0, marginTop: "1px" }} />
        <span>
          {practice
            ? "Practice only. Your code is not compiled, run, saved, submitted or assessed — this is the interview editor to get familiar with, nothing more."
            : "Your code is not compiled or run here. It is read and assessed as part of your final report, so make your approach and complexity clear in comments. You have one submission."}
        </span>
      </div>

      <textarea
        value={code}
        onChange={(e) => {
          setCode(e.target.value);
          setTouched(true);
          setConfirming(false);
        }}
        readOnly={locked}
        spellCheck={false}
        rows={18}
        aria-label={`Solution in ${LANGUAGE_LABELS[language]}`}
        style={{
          width: "100%",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          fontSize: "0.85rem",
          lineHeight: 1.5,
          tabSize: 4,
          background: "#0d1117",
          color: "#e6edf3",
          border: "1px solid #1e293b",
          borderRadius: "10px",
          padding: "1rem",
          outline: "none",
          resize: "vertical",
          opacity: locked ? 0.75 : 1,
        }}
      />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginTop: "1rem", flexWrap: "wrap" }}>
        <span style={{ fontSize: "0.78rem", color: !practice && submitted ? "var(--accent-emerald)" : "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.35rem" }}>
          {practice ? (
            `Practising in ${LANGUAGE_LABELS[language]} — nothing here is submitted`
          ) : submitted ? (
            <>
              <Lock size={14} /> Submitted. This solution is final.
            </>
          ) : confirming ? (
            "This is your only submission. Send it?"
          ) : (
            `Writing in ${LANGUAGE_LABELS[language]}`
          )}
        </span>

        {/* No submit control in practice mode: there is no interview turn to
            submit to, so any button here would be claiming something untrue. */}
        {!practice && !submitted && (
          <button
            onClick={handleSubmit}
            disabled={locked || !code.trim()}
            className="btn btn-primary"
            style={{ padding: "0.6rem 1.25rem", fontSize: "0.85rem" }}
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}{" "}
            <span>{submitting ? "Submitting..." : confirming ? "Confirm final submission" : "Submit solution"}</span>
          </button>
        )}
      </div>
    </div>
  );
};
