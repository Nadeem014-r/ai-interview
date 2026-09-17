"use client";

import React from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  User,
  Zap
} from "lucide-react";

/**
 * Feature content is unchanged from the previous landing page — only the
 * presentation moved to the dark premium theme. Kept as data so the four
 * cards share one layout instead of four copies of the same markup.
 */
const FEATURES = [
  {
    title: "Resume Intelligence",
    description:
      "Extracts verified technical skills, project details, and educational background to evaluate role compatibility.",
    accent: "#a78bfa",
    glow: "rgba(167, 139, 250, 0.45)",
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M6 2H14L19 7V20C19 21.1 18.1 22 17 22H6C4.9 22 4 21.1 4 20V4C4 2.9 4.9 2 6 2Z"
          fill="#a78bfa"
          fillOpacity="0.22"
          stroke="#c4b5fd"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M14 2V7H19" stroke="#c4b5fd" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="16" cy="17" r="5" fill="#8b5cf6" />
        <path d="M14 17L15.5 18.5L18.5 15.5" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  },
  {
    title: "AI Mock Interviews",
    description:
      "Targeted technical interviews across Text, Voice, and Video formats with conversational question progression.",
    accent: "#818cf8",
    glow: "rgba(129, 140, 248, 0.45)",
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="14" height="14" rx="3" fill="#6366f1" fillOpacity="0.28" stroke="#a5b4fc" strokeWidth="1.8" />
        <rect x="8.5" y="8.5" width="7" height="7" rx="1.5" fill="#818cf8" />
        <path
          d="M9 2V5M15 2V5M9 19V22M15 19V22M2 9H5M2 15H5M19 9H22M19 15H22"
          stroke="#a5b4fc"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    )
  },
  {
    title: "Company & Role Grounding",
    description:
      "Tailored preparation matching real-world job requirements, engineering domains, and difficulty expectations.",
    accent: "#34d399",
    glow: "rgba(52, 211, 153, 0.4)",
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M3 21H21M5 21V5C5 3.9 5.9 3 7 3H13C14.1 3 15 3.9 15 5V21M15 9H18C19.1 9 20 9.9 20 11V21"
          stroke="#6ee7b7"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M8 7H12M8 11H12M8 15H12M17 13H18M17 17H18" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    )
  },
  {
    title: "Performance Feedback",
    description:
      "Comprehensive scoring analytics with demonstrated strengths, identified growth areas, and recommendations.",
    accent: "#fbbf24",
    glow: "rgba(251, 191, 36, 0.4)",
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 20H20" stroke="#fcd34d" strokeWidth="1.8" strokeLinecap="round" />
        <rect x="6" y="11" width="3" height="9" rx="1" fill="#fbbf24" />
        <rect x="11" y="6" width="3" height="14" rx="1" fill="#fb923c" />
        <rect x="16" y="13" width="3" height="7" rx="1" fill="#fcd34d" />
      </svg>
    )
  }
];

export default function LandingPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        color: "var(--text-primary)",
        position: "relative",
        overflowX: "hidden",
        fontFamily: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
      }}
    >
      {/* ================= Atmosphere ================= */}
      {/* Drifting accent orbs behind the hero. Purely decorative and
          pointer-transparent, so nothing below changes hit-testing. */}
      <div
        aria-hidden="true"
        style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 0 }}
      >
        <div
          className="orb"
          style={{
            top: "-180px",
            left: "-140px",
            width: "620px",
            height: "620px",
            background: "radial-gradient(circle, rgba(109, 92, 255, 0.5) 0%, rgba(109, 92, 255, 0) 68%)"
          }}
        />
        <div
          className="orb"
          style={{
            top: "-120px",
            right: "-160px",
            width: "560px",
            height: "560px",
            background: "radial-gradient(circle, rgba(168, 85, 247, 0.42) 0%, rgba(168, 85, 247, 0) 68%)",
            animationDelay: "-6s"
          }}
        />
        <div
          className="orb"
          style={{
            top: "540px",
            left: "38%",
            width: "520px",
            height: "520px",
            background: "radial-gradient(circle, rgba(56, 189, 248, 0.26) 0%, rgba(56, 189, 248, 0) 70%)",
            animationDelay: "-11s"
          }}
        />

        {/* Soft flowing waves, restated in the dark palette. */}
        <svg
          style={{
            position: "absolute",
            top: "70px",
            left: 0,
            width: "100%",
            height: "560px",
            opacity: 0.75
          }}
          viewBox="0 0 1440 560"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="none"
        >
          <path
            d="M -100 240 C 260 120, 480 340, 800 220 C 1120 100, 1340 300, 1540 210"
            stroke="url(#waveA)"
            strokeWidth="1.2"
            strokeDasharray="4 6"
          />
          <path
            d="M -80 310 C 220 180, 560 390, 880 260 C 1180 130, 1380 330, 1540 270"
            stroke="url(#waveB)"
            strokeWidth="1.1"
          />
          <path
            d="M -60 380 C 300 250, 640 440, 960 320 C 1220 200, 1420 380, 1540 330"
            stroke="url(#waveA)"
            strokeWidth="0.9"
          />
          <defs>
            <linearGradient id="waveA" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6d5cff" stopOpacity="0" />
              <stop offset="35%" stopColor="#8b7dff" stopOpacity="0.75" />
              <stop offset="70%" stopColor="#c084fc" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#c084fc" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="waveB" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0" />
              <stop offset="50%" stopColor="#7dd3fc" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>

        {/* Dot-grid accents, retained from the original composition. */}
        <div
          style={{
            position: "absolute",
            top: "150px",
            left: "30px",
            width: "90px",
            height: "150px",
            backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.22) 1.5px, transparent 1.5px)",
            backgroundSize: "15px 15px"
          }}
        />
        <div
          style={{
            position: "absolute",
            top: "150px",
            right: "30px",
            width: "90px",
            height: "150px",
            backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.22) 1.5px, transparent 1.5px)",
            backgroundSize: "15px 15px"
          }}
        />
      </div>

      {/* ================= Content ================= */}
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "100%",
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "4.5rem 1.5rem 6rem",
          position: "relative",
          zIndex: 1
        }}
      >
        {/* TOP BADGE */}
        <div
          className="rise-in"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.55rem",
            padding: "0.4rem 1.15rem",
            background: "rgba(255, 255, 255, 0.05)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            border: "1px solid rgba(139, 125, 255, 0.32)",
            borderRadius: "9999px",
            fontSize: "0.72rem",
            fontWeight: 700,
            color: "#c7c2ff",
            letterSpacing: "0.1em",
            boxShadow: "0 0 30px -8px rgba(124, 92, 255, 0.6), 0 1px 0 rgba(255, 255, 255, 0.1) inset",
            marginBottom: "2rem"
          }}
        >
          <Sparkles size={13} color="#a79bff" />
          <span>AI-POWERED PLACEMENT INTELLIGENCE</span>
        </div>

        {/* MAIN BRAND: OfferScript */}
        <div
          className="rise-in"
          style={{
            fontSize: "clamp(3.5rem, 7.5vw, 5.75rem)",
            fontWeight: 800,
            letterSpacing: "-0.05em",
            lineHeight: 1,
            marginBottom: "1rem",
            textAlign: "center",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            animationDelay: "0.05s"
          }}
        >
          <span style={{ color: "#ffffff", position: "relative" }}>
            {/* Lens dot accent above the O */}
            <span
              style={{
                position: "absolute",
                top: "-2px",
                left: "2px",
                width: "9px",
                height: "9px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #8b7dff, #c084fc)",
                boxShadow: "0 0 14px 2px rgba(139, 125, 255, 0.9)"
              }}
            />
            Offer
          </span>
          <span className="gradient-text">Script</span>
        </div>

        {/* MAIN HEADLINE */}
        <div
          className="rise-in"
          style={{
            textAlign: "center",
            marginBottom: "1.5rem",
            position: "relative",
            display: "inline-block",
            animationDelay: "0.1s"
          }}
        >
          <h1
            style={{
              fontSize: "clamp(2rem, 4.6vw, 3.4rem)",
              fontWeight: 750,
              letterSpacing: "-0.038em",
              lineHeight: 1.14,
              margin: 0,
              color: "#f4f5ff",
              textShadow: "0 2px 30px rgba(0, 0, 0, 0.5)"
            }}
          >
            Get hired{" "}
            <span className="gradient-text" style={{ position: "relative" }}>
              with confidence.
            </span>
          </h1>

          {/* Sparkle accent */}
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              top: "-10px",
              right: "-22px",
              color: "#a79bff",
              fontSize: "1.15rem",
              fontWeight: 700,
              pointerEvents: "none",
              textShadow: "0 0 12px rgba(139, 125, 255, 0.9)"
            }}
          >
            ✦
          </span>

          {/* Glowing flourish underline */}
          <svg
            aria-hidden="true"
            style={{ display: "block", margin: "0.4rem auto 0", width: "300px", height: "12px", pointerEvents: "none" }}
            viewBox="0 0 300 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M 12 6 Q 150 11 288 4" stroke="url(#underlineGrad)" strokeWidth="2.5" strokeLinecap="round" />
            <defs>
              <linearGradient id="underlineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8b7dff" stopOpacity="0" />
                <stop offset="50%" stopColor="#a79bff" stopOpacity="1" />
                <stop offset="100%" stopColor="#c084fc" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* SUPPORTING DESCRIPTION */}
        <p
          className="rise-in"
          style={{
            fontSize: "1.08rem",
            color: "var(--text-secondary)",
            maxWidth: "640px",
            textAlign: "center",
            lineHeight: 1.65,
            margin: "0 0 2.5rem",
            fontWeight: 400,
            animationDelay: "0.15s"
          }}
        >
          AI-powered mock interviews, resume intelligence, target company
          preparation, and performance analytics — all in one unified workspace.
        </p>

        {/* CTA BUTTONS */}
        <div
          className="rise-in"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "1rem",
            flexWrap: "wrap",
            marginBottom: "5.5rem",
            animationDelay: "0.2s"
          }}
        >
          <Link
            href="/register"
            className="btn btn-primary hover-lift"
            style={{ padding: "0.9rem 1.9rem", fontSize: "0.95rem", borderRadius: "12px" }}
          >
            <Zap size={15} fill="#ffffff" color="#ffffff" />
            <span>Get Started</span>
            <ArrowRight size={15} />
          </Link>

          <Link
            href="/login"
            className="btn btn-secondary hover-lift"
            style={{ padding: "0.9rem 1.8rem", fontSize: "0.95rem", borderRadius: "12px" }}
          >
            <User size={16} />
            <span>Sign In</span>
          </Link>
        </div>

        {/* SECTION LABEL */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            marginBottom: "0.85rem"
          }}
        >
          <div
            style={{
              width: "38px",
              height: "1px",
              background: "linear-gradient(90deg, rgba(139, 125, 255, 0), rgba(139, 125, 255, 0.8))"
            }}
          />
          <span style={{ color: "#a79bff", fontSize: "0.75rem" }}>✦</span>
          <span
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              color: "#b8b2ff",
              textTransform: "uppercase",
              letterSpacing: "0.16em"
            }}
          >
            PLACEMENT INTELLIGENCE
          </span>
          <span style={{ color: "#a79bff", fontSize: "0.75rem" }}>✦</span>
          <div
            style={{
              width: "38px",
              height: "1px",
              background: "linear-gradient(90deg, rgba(139, 125, 255, 0.8), rgba(139, 125, 255, 0))"
            }}
          />
        </div>

        {/* SECTION HEADING */}
        <div style={{ textAlign: "center", marginBottom: "3.5rem", position: "relative", display: "inline-block" }}>
          <h2
            style={{
              fontSize: "clamp(1.75rem, 3.6vw, 2.5rem)",
              fontWeight: 750,
              letterSpacing: "-0.032em",
              margin: 0,
              color: "#f4f5ff"
            }}
          >
            Everything you need for{" "}
            <span className="gradient-text">interview readiness</span>
          </h2>

          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              top: "-14px",
              right: "-24px",
              color: "#a79bff",
              fontSize: "1.15rem",
              fontWeight: 800,
              pointerEvents: "none",
              textShadow: "0 0 12px rgba(139, 125, 255, 0.8)"
            }}
          >
            ヾ
          </span>

          <svg
            aria-hidden="true"
            style={{ display: "block", margin: "0.4rem auto 0", width: "250px", height: "10px", pointerEvents: "none" }}
            viewBox="0 0 250 10"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M 10 5 Q 125 9 240 3" stroke="url(#headingUnderlineGrad)" strokeWidth="2.2" strokeLinecap="round" />
            <defs>
              <linearGradient id="headingUnderlineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8b7dff" stopOpacity="0" />
                <stop offset="50%" stopColor="#a79bff" stopOpacity="1" />
                <stop offset="100%" stopColor="#c084fc" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* FEATURE CARDS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
            gap: "1.35rem",
            width: "100%",
            maxWidth: "1240px"
          }}
        >
          {FEATURES.map((feature, i) => (
            <div
              key={feature.title}
              className="premium-card rise-in"
              style={{
                padding: "2rem 1.7rem 1.7rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                minHeight: "318px",
                animationDelay: `${0.25 + i * 0.07}s`
              }}
            >
              <div>
                {/* Glowing icon tile */}
                <div
                  style={{
                    width: "58px",
                    height: "58px",
                    borderRadius: "16px",
                    background: `linear-gradient(150deg, ${feature.accent}33 0%, ${feature.accent}14 100%)`,
                    border: `1px solid ${feature.accent}44`,
                    boxShadow: `0 10px 26px -10px ${feature.glow}, inset 0 1px 0 rgba(255, 255, 255, 0.14)`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "1.4rem"
                  }}
                >
                  {feature.icon}
                </div>

                <h3
                  style={{
                    fontSize: "1.125rem",
                    fontWeight: 700,
                    color: "#f2f3ff",
                    margin: "0 0 0.55rem",
                    letterSpacing: "-0.022em"
                  }}
                >
                  {feature.title}
                </h3>

                {/* Accent underline */}
                <div
                  style={{
                    width: "26px",
                    height: "3px",
                    background: `linear-gradient(90deg, ${feature.accent}, ${feature.accent}00)`,
                    borderRadius: "2px",
                    marginBottom: "0.9rem",
                    boxShadow: `0 0 10px ${feature.glow}`
                  }}
                />

                <p
                  style={{
                    color: "var(--text-secondary)",
                    fontSize: "0.875rem",
                    lineHeight: 1.6,
                    margin: 0,
                    fontWeight: 400
                  }}
                >
                  {feature.description}
                </p>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                <div
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "50%",
                    background: "rgba(255, 255, 255, 0.06)",
                    border: `1px solid ${feature.accent}3d`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: feature.accent
                  }}
                >
                  <ArrowRight size={15} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
