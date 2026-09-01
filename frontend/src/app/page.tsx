"use client";

import React from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  User,
  Zap
} from "lucide-react";

export default function LandingPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "#ffffff",
        color: "#09090b",
        position: "relative",
        overflowX: "hidden",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif"
      }}
    >
      {/* Background Decorative Soft Flowing Waves */}
      <svg
        style={{
          position: "absolute",
          top: "60px",
          left: 0,
          width: "100%",
          height: "560px",
          pointerEvents: "none",
          zIndex: 0,
          opacity: 0.45
        }}
        viewBox="0 0 1440 560"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M -100 240 C 260 120, 480 340, 800 220 C 1120 100, 1340 300, 1540 210"
          stroke="url(#purpleWave1)"
          strokeWidth="1.2"
          strokeDasharray="4 4"
        />
        <path
          d="M -80 310 C 220 180, 560 390, 880 260 C 1180 130, 1380 330, 1540 270"
          stroke="url(#purpleWave2)"
          strokeWidth="1"
        />
        <path
          d="M -60 380 C 300 250, 640 440, 960 320 C 1220 200, 1420 380, 1540 330"
          stroke="url(#purpleWave1)"
          strokeWidth="0.8"
        />
        <defs>
          <linearGradient id="purpleWave1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#c7d2fe" stopOpacity="0.1" />
            <stop offset="35%" stopColor="#818cf8" stopOpacity="0.55" />
            <stop offset="70%" stopColor="#c084fc" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#e9d5ff" stopOpacity="0.1" />
          </linearGradient>
          <linearGradient id="purpleWave2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#e9d5ff" stopOpacity="0.05" />
            <stop offset="50%" stopColor="#6366f1" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#a855f7" stopOpacity="0.05" />
          </linearGradient>
        </defs>
      </svg>

      {/* Decorative Dot Grid Accents */}
      <div
        style={{
          position: "absolute",
          top: "140px",
          left: "30px",
          width: "90px",
          height: "140px",
          backgroundImage: "radial-gradient(#e2e8f0 1.5px, transparent 1.5px)",
          backgroundSize: "15px 15px",
          opacity: 0.75,
          pointerEvents: "none",
          zIndex: 0
        }}
      />
      <div
        style={{
          position: "absolute",
          top: "140px",
          right: "30px",
          width: "90px",
          height: "140px",
          backgroundImage: "radial-gradient(#e2e8f0 1.5px, transparent 1.5px)",
          backgroundSize: "15px 15px",
          opacity: 0.75,
          pointerEvents: "none",
          zIndex: 0
        }}
      />

      {/* Main Container */}
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "100%",
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "3.5rem 1.5rem 5rem",
          position: "relative",
          zIndex: 1
        }}
      >
        {/* TOP BADGE */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.35rem 1.1rem",
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "9999px",
            fontSize: "0.725rem",
            fontWeight: 700,
            color: "#4338ca",
            letterSpacing: "0.08em",
            boxShadow: "0 2px 6px rgba(0, 0, 0, 0.03)",
            marginBottom: "1.75rem"
          }}
        >
          <span style={{ color: "#6366f1", fontSize: "0.85rem", display: "inline-flex", alignItems: "center" }}>✦</span>
          <span>AI-POWERED PLACEMENT INTELLIGENCE</span>
        </div>

        {/* MAIN BRAND: OfferScript with dot on O */}
        <div
          style={{
            fontSize: "clamp(3.5rem, 7vw, 5.25rem)",
            fontWeight: 900,
            letterSpacing: "-0.045em",
            lineHeight: 1,
            marginBottom: "0.75rem",
            textAlign: "center",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative"
          }}
        >
          <span style={{ color: "#09090b", position: "relative" }}>
            {/* Small camera/lens dot accent above O */}
            <span
              style={{
                position: "absolute",
                top: "-2px",
                left: "2px",
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#09090b"
              }}
            />
            Offer
          </span>
          <span
            style={{
              background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent"
            }}
          >
            Script
          </span>
        </div>

        {/* MAIN HEADLINE with flourish underline & sparkle */}
        <div
          style={{
            textAlign: "center",
            marginBottom: "1.35rem",
            position: "relative",
            display: "inline-block"
          }}
        >
          <h1
            style={{
              fontSize: "clamp(2rem, 4.4vw, 3.25rem)",
              fontWeight: 800,
              letterSpacing: "-0.035em",
              lineHeight: 1.15,
              margin: 0,
              color: "#09090b"
            }}
          >
            Get hired{" "}
            <span
              style={{
                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                position: "relative"
              }}
            >
              with confidence.
            </span>
          </h1>

          {/* Sparkle Star on top right of "confidence." */}
          <span
            style={{
              position: "absolute",
              top: "-8px",
              right: "-20px",
              color: "#6366f1",
              fontSize: "1.1rem",
              fontWeight: 700,
              pointerEvents: "none"
            }}
          >
            ✦
          </span>

          {/* Subtle curved glowing flourish underline beneath "with confidence." */}
          <svg
            style={{
              display: "block",
              margin: "0.25rem auto 0",
              width: "280px",
              height: "10px",
              pointerEvents: "none"
            }}
            viewBox="0 0 280 10"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M 10 5 Q 140 9 270 3"
              stroke="url(#underlineGrad)"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <defs>
              <linearGradient id="underlineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#818cf8" stopOpacity="0.2" />
                <stop offset="50%" stopColor="#6366f1" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#a855f7" stopOpacity="0.2" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* SUPPORTING DESCRIPTION */}
        <p
          style={{
            fontSize: "1.05rem",
            color: "#64748b",
            maxWidth: "620px",
            textAlign: "center",
            lineHeight: 1.6,
            margin: "0 0 2.25rem",
            fontWeight: 400
          }}
        >
          AI-powered mock interviews, resume intelligence, target company
          preparation, and performance analytics — all in one unified workspace.
        </p>

        {/* CTA BUTTONS */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "1rem",
            flexWrap: "wrap",
            marginBottom: "4.5rem"
          }}
        >
          {/* Primary CTA: Get Started */}
          <Link
            href="/register"
            style={{
              backgroundColor: "#09090b",
              color: "#ffffff",
              padding: "0.85rem 1.85rem",
              borderRadius: "12px",
              fontSize: "0.95rem",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: "0.55rem",
              textDecoration: "none",
              boxShadow: "0 10px 24px -4px rgba(79, 70, 229, 0.42), 0 2px 6px rgba(0, 0, 0, 0.2)",
              transition: "transform 0.15s ease, box-shadow 0.15s ease"
            }}
          >
            <Zap size={15} fill="#ffffff" color="#ffffff" />
            <span>Get Started</span>
            <ArrowRight size={15} />
          </Link>

          {/* Secondary CTA: Sign In */}
          <Link
            href="/login"
            style={{
              backgroundColor: "#ffffff",
              color: "#09090b",
              padding: "0.85rem 1.75rem",
              borderRadius: "12px",
              fontSize: "0.95rem",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: "0.55rem",
              textDecoration: "none",
              border: "1px solid #e2e8f0",
              boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
              transition: "transform 0.15s ease, background-color 0.15s ease"
            }}
          >
            <User size={16} color="#09090b" />
            <span>Sign In</span>
          </Link>
        </div>

        {/* PLACEMENT INTELLIGENCE SECTION LABEL */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            marginBottom: "0.65rem"
          }}
        >
          <div style={{ width: "30px", height: "1px", backgroundColor: "#c7d2fe" }} />
          <span style={{ color: "#6366f1", fontSize: "0.75rem" }}>✦</span>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: "#4f46e5",
              textTransform: "uppercase",
              letterSpacing: "0.12em"
            }}
          >
            PLACEMENT INTELLIGENCE
          </span>
          <span style={{ color: "#6366f1", fontSize: "0.75rem" }}>✦</span>
          <div style={{ width: "30px", height: "1px", backgroundColor: "#c7d2fe" }} />
        </div>

        {/* SECTION HEADING with underline and celebratory dashes */}
        <div style={{ textAlign: "center", marginBottom: "3.25rem", position: "relative", display: "inline-block" }}>
          <h2
            style={{
              fontSize: "clamp(1.75rem, 3.5vw, 2.35rem)",
              fontWeight: 800,
              letterSpacing: "-0.03em",
              margin: 0,
              color: "#09090b"
            }}
          >
            Everything you need for{" "}
            <span
              style={{
                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #7c3aed 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                position: "relative"
              }}
            >
              interview readiness
            </span>
          </h2>

          {/* Celebratory 3 accent lines on upper right of heading */}
          <span
            style={{
              position: "absolute",
              top: "-12px",
              right: "-22px",
              color: "#6366f1",
              fontSize: "1.15rem",
              fontWeight: 800,
              pointerEvents: "none"
            }}
          >
            ヾ
          </span>

          {/* Subtle curved underline under "interview readiness" */}
          <svg
            style={{
              display: "block",
              margin: "0.25rem auto 0",
              width: "240px",
              height: "8px",
              pointerEvents: "none"
            }}
            viewBox="0 0 240 8"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M 10 4 Q 120 7 230 2"
              stroke="url(#headingUnderlineGrad)"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
            <defs>
              <linearGradient id="headingUnderlineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#818cf8" stopOpacity="0.2" />
                <stop offset="50%" stopColor="#6366f1" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#a855f7" stopOpacity="0.2" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* 4 FEATURE CARDS ROW */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
            gap: "1.35rem",
            width: "100%",
            maxWidth: "1240px"
          }}
        >
          {/* CARD 1: Resume Intelligence */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f5f9",
              borderRadius: "20px",
              padding: "2rem 1.65rem 1.65rem",
              boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.04), 0 2px 6px -1px rgba(0, 0, 0, 0.02)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "310px",
              transition: "transform 0.15s ease, box-shadow 0.15s ease"
            }}
          >
            <div>
              {/* 3D-styled Icon Container */}
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "16px",
                  background: "linear-gradient(145deg, #ede9fe 0%, #ddd6fe 100%)",
                  boxShadow: "0 8px 16px -2px rgba(124, 58, 237, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.35rem",
                  position: "relative"
                }}
              >
                {/* SVG 3D Document with check badge */}
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M6 2H14L19 7V20C19 21.1 18.1 22 17 22H6C4.9 22 4 21.1 4 20V4C4 2.9 4.9 2 6 2Z"
                    fill="#8b5cf6"
                    fillOpacity="0.25"
                    stroke="#6d28d9"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path d="M14 2V7H19" stroke="#6d28d9" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  <circle cx="16" cy="17" r="5" fill="#6d28d9" />
                  <path d="M14 17L15.5 18.5L18.5 15.5" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>

              {/* Title */}
              <h3 style={{ fontSize: "1.125rem", fontWeight: 800, color: "#09090b", margin: "0 0 0.5rem", letterSpacing: "-0.02em" }}>
                Resume Intelligence
              </h3>

              {/* Accent Line */}
              <div
                style={{
                  width: "24px",
                  height: "3px",
                  backgroundColor: "#7c3aed",
                  borderRadius: "2px",
                  marginBottom: "0.85rem"
                }}
              />

              {/* Description */}
              <p style={{ color: "#64748b", fontSize: "0.865rem", lineHeight: 1.55, margin: 0, fontWeight: 400 }}>
                Extracts verified technical skills, project details, and educational background to evaluate role compatibility.
              </p>
            </div>

            {/* Bottom Circular Arrow */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.04)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#7c3aed"
                }}
              >
                <ArrowRight size={15} />
              </div>
            </div>
          </div>

          {/* CARD 2: AI Mock Interviews */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f5f9",
              borderRadius: "20px",
              padding: "2rem 1.65rem 1.65rem",
              boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.04), 0 2px 6px -1px rgba(0, 0, 0, 0.02)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "310px",
              transition: "transform 0.15s ease, box-shadow 0.15s ease"
            }}
          >
            <div>
              {/* 3D-styled Icon Container */}
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "16px",
                  background: "linear-gradient(145deg, #e0e7ff 0%, #c7d2fe 100%)",
                  boxShadow: "0 8px 16px -2px rgba(79, 70, 229, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.35rem"
                }}
              >
                {/* SVG 3D AI Chip icon */}
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="5" y="5" width="14" height="14" rx="3" fill="#4f46e5" fillOpacity="0.25" stroke="#3730a3" strokeWidth="1.8" />
                  <rect x="8.5" y="8.5" width="7" height="7" rx="1.5" fill="#4338ca" />
                  <path d="M9 2V5M15 2V5M9 19V22M15 19V22M2 9H5M2 15H5M19 9H22M19 15H22" stroke="#3730a3" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </div>

              {/* Title */}
              <h3 style={{ fontSize: "1.125rem", fontWeight: 800, color: "#09090b", margin: "0 0 0.5rem", letterSpacing: "-0.02em" }}>
                AI Mock Interviews
              </h3>

              {/* Accent Line */}
              <div
                style={{
                  width: "24px",
                  height: "3px",
                  backgroundColor: "#4f46e5",
                  borderRadius: "2px",
                  marginBottom: "0.85rem"
                }}
              />

              {/* Description */}
              <p style={{ color: "#64748b", fontSize: "0.865rem", lineHeight: 1.55, margin: 0, fontWeight: 400 }}>
                Targeted technical interviews across Text, Voice, and Video formats with conversational question progression.
              </p>
            </div>

            {/* Bottom Circular Arrow */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.04)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#4f46e5"
                }}
              >
                <ArrowRight size={15} />
              </div>
            </div>
          </div>

          {/* CARD 3: Company & Role Grounding */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f5f9",
              borderRadius: "20px",
              padding: "2rem 1.65rem 1.65rem",
              boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.04), 0 2px 6px -1px rgba(0, 0, 0, 0.02)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "310px",
              transition: "transform 0.15s ease, box-shadow 0.15s ease"
            }}
          >
            <div>
              {/* 3D-styled Icon Container */}
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "16px",
                  background: "linear-gradient(145deg, #d1fae5 0%, #a7f3d0 100%)",
                  boxShadow: "0 8px 16px -2px rgba(16, 185, 129, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.35rem"
                }}
              >
                {/* SVG 3D Building icon */}
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 21H21M5 21V5C5 3.9 5.9 3 7 3H13C14.1 3 15 3.9 15 5V21M15 9H18C19.1 9 20 9.9 20 11V21" stroke="#065f46" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M8 7H12M8 11H12M8 15H12M17 13H18M17 17H18" stroke="#047857" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </div>

              {/* Title */}
              <h3 style={{ fontSize: "1.125rem", fontWeight: 800, color: "#09090b", margin: "0 0 0.5rem", letterSpacing: "-0.02em" }}>
                Company & Role Grounding
              </h3>

              {/* Accent Line */}
              <div
                style={{
                  width: "24px",
                  height: "3px",
                  backgroundColor: "#10b981",
                  borderRadius: "2px",
                  marginBottom: "0.85rem"
                }}
              />

              {/* Description */}
              <p style={{ color: "#64748b", fontSize: "0.865rem", lineHeight: 1.55, margin: 0, fontWeight: 400 }}>
                Tailored preparation matching real-world job requirements, engineering domains, and difficulty expectations.
              </p>
            </div>

            {/* Bottom Circular Arrow */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.04)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#10b981"
                }}
              >
                <ArrowRight size={15} />
              </div>
            </div>
          </div>

          {/* CARD 4: Performance Feedback */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f5f9",
              borderRadius: "20px",
              padding: "2rem 1.65rem 1.65rem",
              boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.04), 0 2px 6px -1px rgba(0, 0, 0, 0.02)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "310px",
              transition: "transform 0.15s ease, box-shadow 0.15s ease"
            }}
          >
            <div>
              {/* 3D-styled Icon Container */}
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "16px",
                  background: "linear-gradient(145deg, #ffedd5 0%, #fed7aa 100%)",
                  boxShadow: "0 8px 16px -2px rgba(245, 158, 11, 0.22), inset 0 1px 1px rgba(255, 255, 255, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.35rem"
                }}
              >
                {/* SVG 3D Bar chart icon */}
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M4 20H20" stroke="#9a3412" strokeWidth="1.8" strokeLinecap="round" />
                  <rect x="6" y="11" width="3" height="9" rx="1" fill="#ea580c" />
                  <rect x="11" y="6" width="3" height="14" rx="1" fill="#c2410c" />
                  <rect x="16" y="13" width="3" height="7" rx="1" fill="#f97316" />
                </svg>
              </div>

              {/* Title */}
              <h3 style={{ fontSize: "1.125rem", fontWeight: 800, color: "#09090b", margin: "0 0 0.5rem", letterSpacing: "-0.02em" }}>
                Performance Feedback
              </h3>

              {/* Accent Line */}
              <div
                style={{
                  width: "24px",
                  height: "3px",
                  backgroundColor: "#f59e0b",
                  borderRadius: "2px",
                  marginBottom: "0.85rem"
                }}
              />

              {/* Description */}
              <p style={{ color: "#64748b", fontSize: "0.865rem", lineHeight: 1.55, margin: 0, fontWeight: 400 }}>
                Comprehensive scoring analytics with demonstrated strengths, identified growth areas, and recommendations.
              </p>
            </div>

            {/* Bottom Circular Arrow */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.04)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#ea580c"
                }}
              >
                <ArrowRight size={15} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
