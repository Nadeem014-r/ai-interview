"use client";

import React from "react";
import { Bot, Mic, Video, MessageSquare, Wind, ShieldCheck } from "lucide-react";

/**
 * Presentation-only preparation screen shown before the first question.
 *
 * The countdown itself is owned by the interview page; this component just
 * renders whatever second it is handed. It makes no claims about background
 * work, so it stays truthful regardless of what the session is doing.
 */

interface InterviewCountdownProps {
  /** Seconds still remaining, counted down by the parent. */
  seconds: number;
  /** Total the countdown started from, used only for the ring geometry. */
  totalSeconds?: number;
  mode: string;
  roleTitle?: string;
  companyName?: string;
  /**
   * The countdown has finished and the screen is now waiting on the candidate
   * to press Begin. Only the wording changes: "starting now" would be a lie
   * when nothing starts until the button is pressed.
   */
  ready?: boolean;
}

type Phase = "settle" | "guidance" | "ready" | "launch";

const RADIUS = 74;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const MODE_GUIDANCE: Record<string, { icon: React.ReactNode; title: string; line: string; accent: string }> = {
  audio: {
    icon: <Mic size={18} />,
    title: "Voice interview",
    line: "Speak naturally and clearly.",
    accent: "#7c3aed"
  },
  video: {
    icon: <Video size={18} />,
    title: "Video interview",
    line: "Check your posture and camera. Speak confidently.",
    accent: "#4f46e5"
  },
  text: {
    icon: <MessageSquare size={18} />,
    title: "Text interview",
    line: "Take your time and structure your answers clearly.",
    accent: "#4f46e5"
  }
};

function getPhase(seconds: number): Phase {
  if (seconds > 20) return "settle";
  if (seconds > 10) return "guidance";
  if (seconds > 3) return "ready";
  return "launch";
}

export const InterviewCountdown: React.FC<InterviewCountdownProps> = ({
  seconds,
  totalSeconds = 30,
  mode,
  roleTitle,
  companyName,
  ready = false
}) => {
  const phase = getPhase(seconds);
  const guidance = MODE_GUIDANCE[mode] || MODE_GUIDANCE.text;
  const accent = phase === "launch" ? "#4f46e5" : guidance.accent;

  const safeTotal = totalSeconds > 0 ? totalSeconds : 30;
  const elapsedRatio = Math.min(1, Math.max(0, (safeTotal - seconds) / safeTotal));
  const dashOffset = CIRCUMFERENCE * (1 - elapsedRatio);

  const heading = ready
    ? "You're ready to begin"
    : phase === "settle"
      ? "Get ready"
      : phase === "guidance"
      ? guidance.title
      : phase === "ready"
      ? "Your interviewer is ready"
      : "Starting now";

  const subline = ready
    ? "Press Begin Interview when you are ready. The first question comes then."
    : phase === "settle"
      ? "Take a deep breath. Your interview begins soon."
      : phase === "guidance"
      ? guidance.line
      : phase === "ready"
      ? "Settle in. The first question comes next."
      : "";

  return (
    <div
      className="saas-card"
      style={{
        padding: "3rem 2rem 2.75rem",
        textAlign: "center",
        background: "linear-gradient(180deg, rgba(28, 31, 58, 0.85) 0%, rgba(16, 18, 38, 0.9) 100%)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "20px",
        boxShadow: "0 24px 60px -20px rgba(0, 0, 0, 0.9), 0 0 60px -18px rgba(124, 92, 255, 0.45)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "460px",
        gap: "1.5rem",
        position: "relative",
        overflow: "hidden"
      }}
      role="status"
      aria-live="polite"
      aria-label={
        ready
          ? `${heading}. Press Begin Interview to start.`
          : `${heading}. Preparation time remaining: ${seconds} seconds.`
      }
    >
      {/* Soft ambient wash — decorative only */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          top: "-160px",
          left: "50%",
          transform: "translateX(-50%)",
          width: "560px",
          height: "360px",
          background: `radial-gradient(ellipse at center, ${accent}14 0%, transparent 70%)`,
          pointerEvents: "none",
          transition: "background 0.6s ease"
        }}
      />

      {/* Session identity — real values passed from the session */}
      <div
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.45rem",
          padding: "0.35rem 0.85rem",
          borderRadius: "9999px",
          border: "1px solid var(--border-subtle)",
          backgroundColor: "var(--bg-surface)",
          fontSize: "0.75rem",
          fontWeight: 600,
          color: "var(--text-secondary)",
          letterSpacing: "0.01em"
        }}
      >
        <Bot size={14} color={accent} />
        <span>
          {roleTitle || "Technical interview"}
          {companyName ? ` · ${companyName}` : ""}
        </span>
      </div>

      {/* Breathing ring + counter */}
      <div
        style={{
          position: "relative",
          width: "196px",
          height: "196px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}
      >
        {/* Breathing halo */}
        <div
          aria-hidden="true"
          className={phase === "launch" ? undefined : "breathe-ring"}
          style={{
            position: "absolute",
            inset: "10px",
            borderRadius: "50%",
            background: `radial-gradient(circle, ${accent}22 0%, ${accent}00 68%)`
          }}
        />

        {/* Progress ring */}
        <svg
          width="196"
          height="196"
          viewBox="0 0 196 196"
          style={{ position: "absolute", transform: "rotate(-90deg)" }}
          aria-hidden="true"
        >
          <circle cx="98" cy="98" r={RADIUS} stroke="rgba(255, 255, 255, 0.08)" strokeWidth="6" fill="none" />
          <circle
            cx="98"
            cy="98"
            r={RADIUS}
            stroke={accent}
            strokeWidth="6"
            strokeLinecap="round"
            fill="none"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={dashOffset}
            style={{ transition: "stroke-dashoffset 1s linear, stroke 0.6s ease" }}
          />
        </svg>

        {/* Counter */}
        <div
          className={phase === "launch" ? undefined : "breathe-core"}
          style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center" }}
        >
          <span
            key={ready ? "ready" : seconds}
            className={phase === "launch" && !ready ? "countdown-pop" : undefined}
            style={{
              display: "block",
              fontSize: ready ? "2.1rem" : phase === "launch" ? "5.25rem" : "3.4rem",
              fontWeight: 800,
              color: "var(--text-primary)",
              lineHeight: 1,
              letterSpacing: "-0.04em",
              fontVariantNumeric: "tabular-nums",
              transition: "font-size 0.35s cubic-bezier(0.16, 1, 0.3, 1)"
            }}
          >
            {ready ? "Ready" : seconds}
          </span>
          {!ready && phase !== "launch" && (
            <span
              style={{
                marginTop: "0.35rem",
                fontSize: "0.7rem",
                fontWeight: 700,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "var(--text-tertiary)"
              }}
            >
              Seconds
            </span>
          )}
        </div>
      </div>

      {/* Phase copy — remounted per phase so it fades between messages */}
      <div key={phase} className="phase-in" style={{ position: "relative", maxWidth: "480px" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.45rem",
            color: accent,
            marginBottom: "0.55rem"
          }}
        >
          {!ready && phase === "settle" && <Wind size={17} />}
          {!ready && phase === "guidance" && guidance.icon}
          {(ready || phase === "ready") && <ShieldCheck size={17} />}
          <h3
            style={{
              fontSize: "1.4rem",
              fontWeight: 700,
              color: "var(--text-primary)",
              margin: 0,
              letterSpacing: "-0.025em"
            }}
          >
            {heading}
          </h3>
        </div>

        {subline && (
          <p style={{ fontSize: "0.95rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.55 }}>{subline}</p>
        )}
      </div>

      {/* Phase rail — shows where you are in the preparation window */}
      <div
        aria-hidden="true"
        style={{ display: "flex", alignItems: "center", gap: "0.4rem", position: "relative" }}
      >
        {(["settle", "guidance", "ready", "launch"] as Phase[]).map((p) => {
          const reached = ["settle", "guidance", "ready", "launch"].indexOf(p) <= ["settle", "guidance", "ready", "launch"].indexOf(phase);
          return (
            <span
              key={p}
              style={{
                width: p === phase ? "28px" : "8px",
                height: "5px",
                borderRadius: "9999px",
                backgroundColor: reached ? accent : "var(--border-subtle)",
                opacity: reached ? (p === phase ? 1 : 0.45) : 1,
                transition: "width 0.4s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.4s ease, opacity 0.4s ease"
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
