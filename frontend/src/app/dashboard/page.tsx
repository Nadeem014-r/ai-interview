"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { getStoredToken, requireAuth } from "@/lib/auth";
import { InterviewSession, Company, JobMatchResult, ResumeItem, CandidateProfile } from "@/types";
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Upload,
  ArrowRight,
  X,
  MessageSquare,
  Mic,
  Video,
  Target,
  TrendingUp,
  FileCheck,
  AudioLines,
  Clock,
  Lightbulb,
  Plus
} from "lucide-react";

/**
 * Eases a number up to its real value once it is known. Purely presentational:
 * the target always comes from the API, and null stays null.
 */
function useCountUp(target: number | null, durationMs = 900): number {
  const [value, setValue] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (target === null || target === undefined) {
      setValue(0);
      return;
    }

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced || target === 0) {
      setValue(target);
      return;
    }

    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step);
      }
    };
    frameRef.current = requestAnimationFrame(step);

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, durationMs]);

  return value;
}

export default function DashboardPage() {
  const router = useRouter();

  const [history, setHistory] = useState<InterviewSession[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [currentResume, setCurrentResume] = useState<ResumeItem | null>(null);
  const [candidateProfile, setCandidateProfile] = useState<CandidateProfile | null>(null);
  const [userName, setUserName] = useState<string>("");
  const [latestReport, setLatestReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<string | null>(null);

  // Upload / Replace State Machine
  const [uploadStatus, setUploadStatus] = useState<"IDLE" | "UPLOADING" | "PROCESSING" | "EXTRACTING" | "READY" | "FAILED">("IDLE");
  const [statusMessage, setStatusMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Interview Mode Modal State
  const [showModeModal, setShowModeModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState<{ companyId: number; roleId: number; title: string } | null>(null);

  useEffect(() => {
    if (requireAuth(router)) {
      loadDashboardData();
    }
  }, []);

  async function loadDashboardData() {
    setLoading(true);
    setErrorState(null);
    try {
      const [histData, compData, matchData, currResumeData, profData, userData]: [any, any, any, any, any, any] = await Promise.all([
        apiRequest("/interviews/history").catch(() => []),
        apiRequest("/companies").catch(() => []),
        apiRequest("/jobs/matches").catch(() => []),
        apiRequest("/resume/current").catch(() => null),
        apiRequest("/profile").catch(() => null),
        apiRequest("/auth/me").catch(() => null)
      ]);
      
      const sessionList = histData || [];
      setHistory(sessionList);
      setCompanies(compData || []);
      setMatches(matchData || []);
      setCurrentResume(currResumeData || null);
      setCandidateProfile(profData || null);

      if (userData && userData.full_name) {
        setUserName(userData.full_name);
      } else if (profData && profData.full_name) {
        setUserName(profData.full_name);
      }

      // Fetch the actual report for the latest completed interview session
      const completedSessions = sessionList.filter((s: any) => s.status === "completed");
      if (completedSessions.length > 0) {
        const latestSessionId = completedSessions[0].id;
        const rep = await apiRequest(`/reports/${latestSessionId}`).catch(() => null);
        setLatestReport(rep);
      } else {
        setLatestReport(null);
      }
    } catch (err: any) {
      console.error("Dashboard fetch error:", err);
      setErrorState("Unable to load placement dashboard. Please verify your connection.");
    } finally {
      setLoading(false);
    }
  }

  const handleFileUpload = async (file: File) => {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setUploadError("File exceeds the maximum allowed size of 10 MB.");
      setUploadStatus("FAILED");
      return;
    }

    setUploadError("");
    setUploadStatus("UPLOADING");
    setStatusMessage("Uploading resume...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = getStoredToken();
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      setTimeout(() => {
        setUploadStatus("PROCESSING");
        setStatusMessage("Processing document & extracting information...");
      }, 450);

      setTimeout(() => {
        setUploadStatus("EXTRACTING");
        setStatusMessage("Analyzing skills & finding matching roles...");
      }, 1100);

      const res = await fetch(`${API_BASE_URL}/resume/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) {
        setUploadStatus("READY");
        setStatusMessage("Complete! Resume parsed successfully.");
        setShowReplaceModal(false);
        await loadDashboardData();
        setTimeout(() => {
          setUploadStatus("IDLE");
          setStatusMessage("");
        }, 1600);
      } else {
        const errData = await res.json().catch(() => ({}));
        setUploadStatus("FAILED");
        setUploadError(errData.detail || "Resume could not be parsed. Please ensure the file is a readable PDF or DOCX.");
      }
    } catch (err: any) {
      setUploadStatus("FAILED");
      setUploadError(err.message || "Network communication error during resume upload.");
    }
  };

  const openInterviewModal = (role?: { companyId: number; roleId: number; title: string }) => {
    if (role) {
      setSelectedRole(role);
    } else if (matches.length > 0) {
      setSelectedRole({
        companyId: matches[0].company_id,
        roleId: matches[0].role_id,
        title: matches[0].role_title
      });
    } else {
      setSelectedRole({ companyId: 1, roleId: 1, title: "Software Engineer" });
    }
    setShowModeModal(true);
  };

  const extractedSkills = currentResume?.resume_profile?.skills || candidateProfile?.skills || [];
  const hasResume = !!currentResume;
  const displayName = userName || candidateProfile?.full_name || "Candidate";
  const firstName = displayName.split(" ")[0] || "Candidate";

  // Dynamic Time-of-Day Greeting
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "Good morning";
    if (hour >= 12 && hour < 17) return "Good afternoon";
    return "Good evening";
  };

  // These four numbers all come from the resume-to-role matcher, and none of
  // them measures interview performance. `overall_score` is a weighted blend of
  // how much of the target role's requirements the resume evidences;
  // `skills_score` in particular is the share of the role's required skills
  // found in the resume, so 100 % means "your resume covers every listed
  // requirement", not "your technical skill is perfect". The maths below is
  // left exactly as the matcher computes it -- only the labels changed, so the
  // card claims what it actually measures.
  const highestMatch = matches.length > 0 ? matches[0] : null;

  const readinessScore = highestMatch ? Math.round(highestMatch.overall_score) : (hasResume ? 0 : null);
  // Describes the strength of the match, which is what the number is. It used
  // to read "Strong" / "Needs Preparation", which sounded like a verdict on the
  // candidate's interview readiness rather than on resume coverage.
  const readinessLabel = readinessScore !== null ? (readinessScore >= 75 ? "Strong match" : readinessScore >= 60 ? "Good match" : readinessScore > 0 ? "Partial match" : "No match yet") : "Pending";

  // Real resume-derived breakdown scores (0% if no evidence exists)
  const techSkillScore = highestMatch?.breakdown?.skills_score != null ? Math.round(highestMatch.breakdown.skills_score) : 0;
  const projectsScore = highestMatch?.breakdown?.projects_score != null ? Math.round(highestMatch.breakdown.projects_score) : 0;
  const expScore = highestMatch?.breakdown?.experience_score != null ? Math.round(highestMatch.breakdown.experience_score) : 0;

  // Target role title & domain
  const targetRoleTitle = highestMatch?.role_title || candidateProfile?.target_role || "Software Engineer";
  const hasTargetRole = !!(highestMatch?.role_title || candidateProfile?.target_role);
  const targetDomain = highestMatch?.role_title?.toLowerCase().includes("frontend")
    ? "Frontend"
    : highestMatch?.role_title?.toLowerCase().includes("full")
    ? "Full Stack"
    : "Backend";

  // When a completed interview actually happened is its end_time, not the
  // created_at the card used to read -- created_at is when the session was
  // configured, which can be days before it was sat. Sessions are ordered by
  // created_at, so "most recent" is also resolved on completion time here.
  const completionTimeOf = (s?: InterviewSession | null) =>
    s ? s.end_time || s.created_at : undefined;

  // FIX #2: Retrieve actual score from the most recent completed interview
  const latestCompletedSession = history
    .filter((s) => s.status === "completed")
    .reduce<InterviewSession | null>((latest, s) => {
      if (!latest) return s;
      const a = new Date(completionTimeOf(s) || 0).getTime();
      const b = new Date(completionTimeOf(latest) || 0).getTime();
      return a > b ? s : latest;
    }, null);
  const hasCompletedInterview = !!latestCompletedSession;
  
  let latestExactScore: number | null = null;
  if (latestReport && latestReport.overall_score != null) {
    latestExactScore = Math.round(latestReport.overall_score);
  } else if (latestCompletedSession) {
    if ((latestCompletedSession as any).overall_score != null) {
      latestExactScore = Math.round((latestCompletedSession as any).overall_score);
    } else if (latestCompletedSession.answers && latestCompletedSession.answers.length > 0) {
      const scoredAnswers = latestCompletedSession.answers.filter((a: any) => a.evaluation?.overall_question_score != null);
      if (scoredAnswers.length > 0) {
        const sum = scoredAnswers.reduce((acc: number, a: any) => acc + (a.evaluation?.overall_question_score || 0), 0);
        latestExactScore = Math.round(sum / scoredAnswers.length);
      }
    }
  }

  const latestRoleTitle = latestCompletedSession?.role_title || (history.length > 0 ? history[0].role_title : "Backend Technical");
  
  // Format relative time helper.
  //
  // The API now sends timestamps with an explicit UTC offset, so Date parses
  // them against the viewer's own clock and no timezone is assumed here. A
  // small negative difference (clock skew between server and browser) reads as
  // "Just now" rather than as a time in the future.
  const getTimeAgo = (dateString?: string) => {
    if (!dateString) return "Recently";
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return "Recently";
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    if (diffMinutes < 1) return "Just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const latestTimeAgo = completionTimeOf(latestCompletedSession)
    ? getTimeAgo(completionTimeOf(latestCompletedSession))
    : history[0]?.created_at
    ? getTimeAgo(history[0].created_at)
    : "Recently";

  // Readiness colour band, so the gauge reads at a glance instead of always
  // being brand indigo regardless of the score.
  const readinessColor =
    readinessScore === null
      ? "#a1a1aa"
      : readinessScore >= 75
      ? "var(--accent-emerald)"
      : readinessScore >= 60
      ? "var(--accent-brand)"
      : readinessScore > 0
      ? "var(--accent-amber)"
      : "var(--text-tertiary)";

  // Animated presentation of values that are already loaded from the API.
  const animatedReadiness = useCountUp(loading ? null : readinessScore);
  const animatedTech = useCountUp(loading ? null : techSkillScore);
  const animatedProjects = useCountUp(loading ? null : projectsScore);
  const animatedExp = useCountUp(loading ? null : expScore);
  const animatedLatestScore = useCountUp(loading ? null : latestExactScore);

  // Top skills actually extracted from the resume, for the Resume Status card.
  const topSkills = extractedSkills.slice(0, 4);

  // Real progress series: one point per completed interview that has scored
  // answers, oldest first. No synthetic points are ever added.
  const scoreTrend: number[] = history
    .filter((sess) => sess.status === "completed")
    .map((sess) => {
      const scored = (sess.answers || []).filter(
        (a: any) => a?.evaluation?.overall_question_score != null
      );
      if (scored.length === 0) return null;
      const avg =
        scored.reduce((acc: number, a: any) => acc + a.evaluation.overall_question_score, 0) /
        scored.length;
      // Per-question scores are out of 10; present on the same 0-100 scale as
      // the rest of the dashboard.
      return Math.round(avg * 10);
    })
    .filter((v): v is number => v !== null)
    .reverse();

  // Real companies already loaded for this candidate, used instead of a fixed
  // set of logos.
  const targetCompanies = (matches.length > 0
    ? matches.slice(0, 3).map((m) => m.company_name)
    : companies.slice(0, 3).map((c) => c.name)
  ).filter(Boolean);

  // SVG Circular Gauge calculation
  const gaugeRadius = 52;
  const circumference = 2 * Math.PI * gaugeRadius;
  const strokeDashoffset =
    readinessScore !== null
      ? circumference - (animatedReadiness / 100) * circumference
      : circumference;

  return (
    <WorkspaceLayout hideHeader={true} contentMaxWidth="1200px">
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".pdf,.docx,.txt"
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFileUpload(e.target.files[0]);
            e.target.value = "";
          }
        }}
      />

      <div style={{ position: "relative", minHeight: "100%" }}>
        {/* Subtle Decorative Background Wave & Sparkles */}
        <div
          style={{
            position: "absolute",
            top: "-20px",
            right: "0",
            left: "0",
            height: "380px",
            pointerEvents: "none",
            zIndex: 0,
            overflow: "hidden",
            opacity: 0.85
          }}
        >
          {/* Subtle curved wave line */}
          <svg
            width="100%"
            height="100%"
            viewBox="0 0 1200 380"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ position: "absolute", top: 0, right: 0 }}
          >
            <path
              d="M350,70 Q600,140 850,50 T1250,90"
              stroke="rgba(99, 102, 241, 0.08)"
              strokeWidth="2.5"
              fill="none"
            />
            <path
              d="M450,110 Q700,180 950,90 T1300,130"
              stroke="rgba(168, 85, 247, 0.06)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              fill="none"
            />
          </svg>

          {/* Subtle floating 4-point sparkle stars */}
          <div style={{ position: "absolute", top: "45px", left: "620px", color: "rgba(99, 102, 241, 0.4)", fontSize: "16px" }}>✦</div>
          <div style={{ position: "absolute", top: "185px", left: "260px", color: "rgba(168, 85, 247, 0.35)", fontSize: "13px" }}>✦</div>
          <div style={{ position: "absolute", top: "190px", right: "290px", color: "rgba(99, 102, 241, 0.4)", fontSize: "14px" }}>✦</div>
          <div style={{ position: "absolute", top: "270px", right: "310px", color: "rgba(168, 85, 247, 0.3)", fontSize: "11px" }}>✦</div>
          <div style={{ position: "absolute", top: "95px", right: "120px", color: "rgba(99, 102, 241, 0.4)", fontSize: "13px" }}>✦</div>
        </div>

        {/* Global Error Banner */}
        {errorState && (
          <div
            style={{
              padding: "0.75rem 1rem",
              backgroundColor: "var(--accent-rose-light)",
              border: "1px solid rgba(251, 113, 133, 0.32)",
              borderRadius: "10px",
              color: "var(--accent-rose)",
              fontSize: "0.85rem",
              marginBottom: "1.5rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              position: "relative",
              zIndex: 1
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <AlertCircle size={16} /> {errorState}
            </div>
            <button onClick={loadDashboardData} className="btn btn-secondary" style={{ padding: "0.25rem 0.6rem", fontSize: "0.75rem" }}>
              Retry
            </button>
          </div>
        )}

        {/* Top Hero Greeting Row with Local Time Greeting */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "2rem",
            position: "relative",
            zIndex: 1
          }}
        >
          <div>
            <div style={{ fontSize: "0.925rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.4rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span>{getGreeting()}, {firstName}.</span> <span>👋</span>
            </div>
            <h1
              style={{
                fontSize: "2.35rem",
                fontWeight: 800,
                color: "var(--text-primary)",
                letterSpacing: "-0.035em",
                lineHeight: 1.15,
                margin: "0 0 0.65rem 0",
                display: "flex",
                alignItems: "center",
                gap: "0.3rem",
                flexWrap: "wrap"
              }}
            >
              <span>Ready for your</span>{" "}
              <span style={{ color: "var(--accent-brand)", position: "relative", display: "inline-flex", alignItems: "center" }}>
                next interview?
                <span
                  style={{
                    position: "absolute",
                    top: "-8px",
                    right: "-18px",
                    color: "var(--accent-brand)",
                    fontSize: "1.1rem",
                    lineHeight: 1
                  }}
                >
                  ✦
                </span>
              </span>
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0, maxWidth: "600px", lineHeight: 1.5 }}>
              Your interview preparation, resume intelligence, and placement progress — all in one place.
            </p>
          </div>

          {/* + New Interview CTA Button */}
          <button
            onClick={() => openInterviewModal()}
            style={{
              backgroundColor: "#6d5cff",
              color: "#ffffff",
              border: "none",
              borderRadius: "10px",
              padding: "0.65rem 1.25rem",
              fontSize: "0.875rem",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: "0.45rem",
              cursor: "pointer",
              boxShadow: "0 10px 26px -10px rgba(124, 92, 255, 0.85), 0 1px 0 rgba(255, 255, 255, 0.2) inset",
              transition: "all 0.15s ease",
              flexShrink: 0
            }}
            className="hover-lift"
          >
            <Plus size={15} strokeWidth={2.5} />
            <span>New Interview</span>
          </button>
        </div>

        {/* Main AI Interview Hero Card */}
        <div
          className="glass-card hover-elevate rise-in"
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "20px",
            boxShadow: "0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 26px 60px -24px rgba(0, 0, 0, 0.9)",
            padding: "2rem 2.75rem",
            marginBottom: "1.75rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "relative",
            overflow: "hidden",
            zIndex: 1
          }}
        >
          {/* Left Side: 3D-styled Polished Microphone Graphic */}
          <div style={{ display: "flex", alignItems: "center", gap: "2.25rem" }}>
            <div
              style={{
                width: "120px",
                height: "120px",
                flexShrink: 0,
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              {/* Pedestal / Shadow Base */}
              <div
                style={{
                  position: "absolute",
                  bottom: "4px",
                  width: "90px",
                  height: "22px",
                  borderRadius: "50%",
                  background: "radial-gradient(ellipse at center, rgba(124, 58, 237, 0.28) 0%, rgba(99, 102, 241, 0.05) 60%, transparent 80%)",
                  filter: "blur(2px)"
                }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: "10px",
                  width: "74px",
                  height: "14px",
                  borderRadius: "50%",
                  background: "linear-gradient(180deg, rgba(167, 155, 255, 0.55) 0%, rgba(124, 92, 255, 0.25) 100%)",
                  boxShadow: "0 0 26px -4px rgba(124, 92, 255, 0.75)"
                }}
              />

              {/* 3D Purple Studio Microphone SVG */}
              <svg width="84" height="98" viewBox="0 0 84 98" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ position: "relative", zIndex: 2 }}>
                <defs>
                  <linearGradient id="micBody" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#a78bfa" />
                    <stop offset="35%" stopColor="#7c3aed" />
                    <stop offset="100%" stopColor="#6366f1" />
                  </linearGradient>
                  <linearGradient id="micHighlight" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#ffffff" stopOpacity="0.65" />
                    <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="standGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#e2e8f0" />
                    <stop offset="50%" stopColor="#cbd5e1" />
                    <stop offset="100%" stopColor="#94a3b8" />
                  </linearGradient>
                </defs>

                {/* Outer U-Mount Frame */}
                <path
                  d="M20 40 C20 54 30 65 42 65 C54 65 64 54 64 40"
                  stroke="url(#standGrad)"
                  strokeWidth="5.5"
                  strokeLinecap="round"
                />
                <path d="M42 65 L42 82" stroke="url(#standGrad)" strokeWidth="6" strokeLinecap="round" />
                <ellipse cx="42" cy="85" rx="20" ry="5.5" fill="url(#standGrad)" />

                {/* Microphone Capsule Body */}
                <rect x="29" y="14" width="26" height="42" rx="13" fill="url(#micBody)" />
                
                {/* Horizontal Mesh Slits */}
                <rect x="33" y="24" width="18" height="2.5" rx="1.2" fill="#ffffff" fillOpacity="0.85" />
                <rect x="33" y="30" width="18" height="2.5" rx="1.2" fill="#ffffff" fillOpacity="0.85" />
                <rect x="34" y="36" width="16" height="2.5" rx="1.2" fill="#ffffff" fillOpacity="0.75" />
                
                {/* Glossy Capsule Reflection */}
                <path d="M31 20 C31 16 34 16 38 15.5 C34 18 33 28 33 38 C33 46 34 50 34 50 C32 48 31 42 31 36 Z" fill="url(#micHighlight)" />
              </svg>

              {/* Little Floating Star */}
              <div style={{ position: "absolute", top: "10px", left: "-6px", color: "#a5b4fc", fontSize: "14px" }}>✦</div>
            </div>

            {/* Center Content */}
            <div>
              <h2
                style={{
                  fontSize: "1.45rem",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                  margin: "0 0 0.35rem 0",
                  letterSpacing: "-0.025em"
                }}
              >
                Start an AI Interview
              </h2>
              <p
                style={{
                  color: "var(--text-muted)",
                  fontSize: "0.9rem",
                  margin: "0 0 1.25rem 0",
                  lineHeight: 1.45,
                  maxWidth: "400px"
                }}
              >
                Practice with AI-powered interviews tailored to your target role.
              </p>
              <button
                onClick={() => openInterviewModal()}
                style={{
                  backgroundColor: "#6d5cff",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "9px",
                  padding: "0.6rem 1.35rem",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.45rem",
                  cursor: "pointer",
                  boxShadow: "0 10px 24px -10px rgba(124, 92, 255, 0.8), 0 1px 0 rgba(255, 255, 255, 0.2) inset",
                  transition: "all 0.15s ease"
                }}
                className="hover-lift"
              >
                <span>Start Interview</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </div>

          {/* Right Side: 3D ID Profile Card + Waveform Graphic */}
          <div
            style={{
              position: "relative",
              width: "240px",
              height: "120px",
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              flexShrink: 0
            }}
            className="feature-graphic-desktop"
          >
            {/* Main Profile ID Card */}
            <div
              style={{
                position: "absolute",
                right: "42px",
                width: "115px",
                height: "82px",
                backgroundColor: "var(--bg-surface)",
                borderRadius: "14px",
                border: "1px solid rgba(139, 125, 255, 0.28)",
                boxShadow: "0 18px 40px -18px rgba(0, 0, 0, 0.9), 0 0 34px -14px rgba(124, 92, 255, 0.65)",
                padding: "0.75rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                transform: "rotate(-4deg)",
                zIndex: 2
              }}
            >
              {/* Profile Avatar & Dot */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div
                  style={{
                    width: "28px",
                    height: "28px",
                    borderRadius: "50%",
                    backgroundColor: "#6d5cff",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 0 16px -2px rgba(139, 125, 255, 0.9)"
                  }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
                  </svg>
                </div>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "3px" }}>
                  <div style={{ width: "24px", height: "4px", backgroundColor: "#6d5cff", borderRadius: "2px" }} />
                  <div style={{ width: "16px", height: "3px", backgroundColor: "var(--accent-brand-light)", borderRadius: "2px" }} />
                </div>
              </div>

              {/* ID Lines */}
              <div style={{ display: "flex", flexDirection: "column", gap: "3.5px" }}>
                <div style={{ width: "100%", height: "4.5px", backgroundColor: "var(--bg-subtle)", borderRadius: "3px" }} />
                <div style={{ width: "70%", height: "4.5px", backgroundColor: "var(--bg-subtle)", borderRadius: "3px" }} />
              </div>
            </div>

            {/* Overlapping Waveform Card */}
            <div
              style={{
                position: "absolute",
                right: "-6px",
                width: "95px",
                height: "76px",
                backgroundColor: "var(--accent-brand-light)",
                borderRadius: "14px",
                border: "1px solid rgba(139, 125, 255, 0.28)",
                boxShadow: "0 16px 38px -16px rgba(0, 0, 0, 0.9), 0 0 30px -14px rgba(168, 85, 247, 0.6)",
                padding: "0.6rem 0.75rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "4px",
                transform: "rotate(6deg)",
                zIndex: 1
              }}
            >
              <div style={{ width: "3.5px", height: "14px", backgroundColor: "#8b7dff", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "24px", backgroundColor: "#6d5cff", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "34px", backgroundColor: "#a855f7", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "20px", backgroundColor: "#6d5cff", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "12px", backgroundColor: "#8b7dff", borderRadius: "2px" }} />
            </div>

            {/* Subtle floating sparkles */}
            <div style={{ position: "absolute", top: "0px", right: "70px", color: "var(--accent-brand)", fontSize: "14px" }}>✦</div>
            <div style={{ position: "absolute", bottom: "-4px", left: "40px", color: "#c084fc", fontSize: "12px" }}>✦</div>
          </div>
        </div>

        {/* Four Insight Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(218px, 1fr))",
            gap: "1.15rem",
            marginBottom: "1.75rem",
            position: "relative",
            zIndex: 1
          }}
        >
          {/* Card 1: Resume-to-role match (from the matcher's breakdown). This
              is coverage of the target role's requirements by the resume, not
              interview readiness and not measured skill. */}
          <div
            className="glass-card hover-elevate rise-in"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "18px",
              boxShadow: "0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 48px -22px rgba(0, 0, 0, 0.88)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px",
              animationDelay: "0ms"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Resume–Role Match
                </h3>
                <TrendingUp size={18} color="var(--accent-brand)" strokeWidth={2.2} />
              </div>

              {/* Circular Gauge */}
              <div style={{ display: "flex", justifyContent: "center", alignItems: "center", margin: "0.65rem 0 1rem" }}>
                <div style={{ position: "relative", width: "120px", height: "120px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <svg width="120" height="120" viewBox="0 0 120 120" style={{ transform: "rotate(-90deg)" }}>
                    {/* Background Track */}
                    <circle
                      cx="60"
                      cy="60"
                      r={gaugeRadius}
                      stroke="rgba(255, 255, 255, 0.07)"
                      strokeWidth="9"
                      fill="none"
                    />
                    {/* Progress Circle */}
                    <circle
                      cx="60"
                      cy="60"
                      r={gaugeRadius}
                      stroke={readinessColor}
                      strokeWidth="9"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                      fill="none"
                      style={{ transition: "stroke 0.5s ease" }}
                    />
                  </svg>
                  {/* Gauge Center Text */}
                  <div style={{ position: "absolute", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ fontSize: "1.65rem", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1, letterSpacing: "-0.03em" }}>
                      {readinessScore !== null ? `${animatedReadiness}%` : "—"}
                    </span>
                    <span style={{ fontSize: "0.78rem", fontWeight: 600, color: readinessColor, marginTop: "3px" }}>
                      {readinessLabel}
                    </span>
                  </div>
                </div>
              </div>

              {/* Says plainly what the percentage is, so a high number is not
                  mistaken for a measure of interview performance. */}
              <p
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-tertiary)",
                  textAlign: "center",
                  lineHeight: 1.45,
                  margin: "0 0 0.7rem"
                }}
              >
                How much of {hasTargetRole ? targetRoleTitle : "your target role"}&rsquo;s requirements
                your resume evidences &mdash; not a score for your interviews.
              </p>

              {/* Breakdown Bars (Derived from Resume Job Match Breakdown) */}
              {highestMatch ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", marginBottom: "0.5rem" }}>
                {/* Share of the role's required skills evidenced in the resume */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--text-muted)", width: "85px" }} title="Share of this role's required skills found in your resume">Skills covered</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "var(--bg-subtle)", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${animatedTech}%`,
                        height: "100%",
                        backgroundColor: readinessColor,
                        borderRadius: "10px",
                        transition: "background-color 0.5s ease"
                      }}
                    />
                  </div>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)", width: "28px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{animatedTech}%</span>
                </div>

                {/* Projects & Domain */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--text-muted)", width: "85px" }} title="Strength of the project evidence in your resume against this role's key topics">Project evidence</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "var(--bg-subtle)", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${animatedProjects}%`,
                        height: "100%",
                        backgroundColor: readinessColor,
                        borderRadius: "10px",
                        transition: "background-color 0.5s ease"
                      }}
                    />
                  </div>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)", width: "28px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{animatedProjects}%</span>
                </div>

                {/* Experience Match */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--text-muted)", width: "85px" }} title="How your recorded work experience lines up with this role's level">Experience fit</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "var(--bg-subtle)", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${animatedExp}%`,
                        height: "100%",
                        backgroundColor: readinessColor,
                        borderRadius: "10px",
                        transition: "background-color 0.5s ease"
                      }}
                    />
                  </div>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)", width: "28px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{animatedExp}%</span>
                </div>
              </div>
              ) : (
                <div
                  style={{
                    padding: "0.85rem 0.9rem",
                    borderRadius: "12px",
                    backgroundColor: "var(--bg-subtle)",
                    border: "1px dashed var(--border-subtle)",
                    fontSize: "0.78rem",
                    color: "var(--text-muted)",
                    lineHeight: 1.5,
                    textAlign: "center"
                  }}
                >
                  {hasResume
                    ? "No role match analysis yet — pick a target role to see your skills, projects and experience breakdown."
                    : "Upload your resume to unlock your role match breakdown."}
                </div>
              )}
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/resume"
                style={{
                  color: "var(--accent-brand)",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem"
                }}
              >
                <span>View Insights</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>

          {/* Card 2: Resume Status */}
          <div
            className="glass-card hover-elevate rise-in"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "18px",
              boxShadow: "0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 48px -22px rgba(0, 0, 0, 0.88)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px",
              animationDelay: "70ms"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Resume Status
                </h3>
                <FileCheck size={18} color="var(--accent-cyan)" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "16px",
                    backgroundColor: "var(--accent-cyan-light)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "0.75rem",
                    boxShadow: "0 0 22px -8px rgba(56, 189, 248, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.12)"
                  }}
                >
                  <svg width="30" height="34" viewBox="0 0 24 28" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="2" y="2" width="20" height="24" rx="4" fill="#3b82f6" />
                    <rect x="5" y="5" width="14" height="18" rx="2" fill="#ffffff" />
                    <rect x="7" y="8" width="10" height="2" rx="1" fill="#93c5fd" />
                    <rect x="7" y="12" width="7" height="2" rx="1" fill="#93c5fd" />
                    <rect x="7" y="16" width="9" height="2" rx="1" fill="#93c5fd" />
                    <circle cx="17" cy="19" r="4.5" fill="#2563eb" />
                    <path d="M15 19 L16.5 20.5 L19.5 17.5" stroke="#ffffff" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>

                {/* Status Pill */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    color: hasResume ? "var(--accent-cyan)" : "var(--accent-amber)",
                    fontSize: "0.9rem",
                    fontWeight: 700,
                    marginBottom: "0.45rem"
                  }}
                >
                  {hasResume ? <CheckCircle2 size={15} color="var(--accent-cyan)" /> : <AlertCircle size={15} color="var(--accent-amber)" />}
                  <span>{hasResume ? "Ready" : "Pending"}</span>
                </div>

                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.55rem" }}>
                  {hasResume ? `${extractedSkills.length || 0} skills detected` : "Upload resume to extract skills"}
                </div>

                {topSkills.length > 0 && (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "0.3rem",
                      justifyContent: "center",
                      marginBottom: "0.6rem"
                    }}
                  >
                    {topSkills.map((skill: string) => (
                      <span
                        key={skill}
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 600,
                          color: "var(--accent-cyan)",
                          backgroundColor: "var(--accent-cyan-light)",
                          border: "1px solid rgba(56, 189, 248, 0.3)",
                          borderRadius: "9999px",
                          padding: "0.15rem 0.5rem",
                          maxWidth: "110px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap"
                        }}
                        title={skill}
                      >
                        {skill}
                      </span>
                    ))}
                    {extractedSkills.length > topSkills.length && (
                      <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-muted)", padding: "0.15rem 0.3rem" }}>
                        +{extractedSkills.length - topSkills.length}
                      </span>
                    )}
                  </div>
                )}

                <div style={{ fontSize: "0.78rem", fontWeight: 500, color: hasTargetRole ? "#6d5cff" : "#a1a1aa" }}>
                  {hasTargetRole ? `${targetRoleTitle} • ${targetDomain}` : "No target role set yet"}
                </div>
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/resume"
                style={{
                  color: "var(--accent-brand)",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem"
                }}
              >
                <span>View Resume</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>

          {/* Card 3: Your Target */}
          <div
            className="glass-card hover-elevate rise-in"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "18px",
              boxShadow: "0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 48px -22px rgba(0, 0, 0, 0.88)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px",
              animationDelay: "140ms"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Your Target
                </h3>
                <Target size={18} color="var(--accent-emerald)" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "50%",
                    backgroundColor: "var(--accent-emerald-light)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "0.75rem",
                    boxShadow: "0 0 22px -8px rgba(52, 211, 153, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.12)"
                  }}
                >
                  <svg width="34" height="34" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="16" cy="16" r="14" stroke="#10b981" strokeWidth="2.5" />
                    <circle cx="16" cy="16" r="9" stroke="#10b981" strokeWidth="2.5" />
                    <circle cx="16" cy="16" r="4.5" fill="#10b981" />
                    <path d="M23 9 L28 4" stroke="#10b981" strokeWidth="2" strokeLinecap="round" />
                    <path d="M25 4 L28 4 L28 7" stroke="#10b981" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </div>

                <div
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    color: hasTargetRole ? "#6d5cff" : "#a1a1aa",
                    marginBottom: "0.2rem"
                  }}
                >
                  {hasTargetRole ? targetRoleTitle : "No target role set yet"}
                </div>

                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.85rem" }}>
                  {hasTargetRole ? targetDomain : "Add one in your profile or upload a resume"}
                </div>

                {/* Match strength for this role, straight from the job-match API */}
                {highestMatch && (
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.35rem",
                      backgroundColor: "var(--accent-emerald-light)",
                      border: "1px solid rgba(52, 211, 153, 0.32)",
                      color: "var(--accent-emerald)",
                      padding: "0.2rem 0.6rem",
                      borderRadius: "9999px",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      marginBottom: "0.7rem"
                    }}
                  >
                    <Target size={11} strokeWidth={2.6} />
                    <span>{Math.round(highestMatch.overall_score)}% role match</span>
                  </div>
                )}

                {/* Companies this candidate actually has roles matched against */}
                {targetCompanies.length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0.35rem" }}>
                    {targetCompanies.map((name) => (
                      <span
                        key={name}
                        title={name}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.3rem",
                          backgroundColor: "var(--bg-surface)",
                          border: "1px solid var(--border-subtle)",
                          borderRadius: "8px",
                          padding: "0.22rem 0.5rem",
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          color: "var(--text-secondary)",
                          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.5)",
                          maxWidth: "120px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap"
                        }}
                      >
                        <span
                          style={{
                            width: "16px",
                            height: "16px",
                            borderRadius: "5px",
                            backgroundColor: "var(--accent-emerald-light)",
                            color: "var(--accent-emerald)",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.62rem",
                            fontWeight: 800,
                            flexShrink: 0
                          }}
                        >
                          {name.charAt(0).toUpperCase()}
                        </span>
                        {name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
                    No matched companies yet
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/companies"
                style={{
                  color: "var(--accent-brand)",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem"
                }}
              >
                <span>Explore Opportunities</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>

          {/* Card 4: Latest Interview (FIX #2: Actual Most Recent Completed Interview Score) */}
          <div
            className="glass-card hover-elevate rise-in"
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "18px",
              boxShadow: "0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 48px -22px rgba(0, 0, 0, 0.88)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px",
              animationDelay: "210ms"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Latest Interview
                </h3>
                <AudioLines size={18} color="var(--accent-brand)" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "16px",
                    backgroundColor: "var(--accent-brand-light)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "3.5px",
                    marginBottom: "0.75rem",
                    boxShadow: "0 0 22px -8px rgba(124, 92, 255, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.12)"
                  }}
                >
                  <div style={{ width: "3.5px", height: "12px", backgroundColor: "#8b7dff", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "22px", backgroundColor: "#6d5cff", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "30px", backgroundColor: "#a855f7", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "18px", backgroundColor: "#6d5cff", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "10px", backgroundColor: "#8b7dff", borderRadius: "2px" }} />
                </div>

                <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.35rem" }}>
                  {hasCompletedInterview ? latestRoleTitle : "No interviews yet"}
                </div>

                {/* Score Pill Badge — FIX #2: Actual score from latest completed interview */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
                    backgroundColor:
                      latestExactScore === null ? "var(--accent-brand-light)" : latestExactScore >= 70 ? "var(--accent-emerald-light)" : latestExactScore >= 50 ? "var(--accent-brand-light)" : "var(--accent-amber-light)",
                    color:
                      latestExactScore === null ? "var(--accent-brand)" : latestExactScore >= 70 ? "var(--accent-emerald)" : latestExactScore >= 50 ? "#4f46e5" : "var(--accent-amber)",
                    padding: "0.22rem 0.65rem",
                    borderRadius: "20px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    marginBottom: "0.45rem",
                    fontVariantNumeric: "tabular-nums",
                    transition: "background-color 0.4s ease, color 0.4s ease"
                  }}
                >
                  {hasCompletedInterview && latestExactScore !== null ? (
                    <>
                      <CheckCircle2 size={12} strokeWidth={2.5} />
                      <span>{animatedLatestScore}/100</span>
                    </>
                  ) : hasCompletedInterview ? (
                    <span>Completed</span>
                  ) : (
                    <span>Pending Practice</span>
                  )}
                </div>

                {/* Score bar — only drawn when a real score exists */}
                {hasCompletedInterview && latestExactScore !== null && (
                  <div
                    style={{
                      width: "88px",
                      height: "5px",
                      borderRadius: "9999px",
                      backgroundColor: "var(--accent-brand-light)",
                      overflow: "hidden",
                      marginBottom: "0.5rem"
                    }}
                    aria-hidden="true"
                  >
                    <div
                      style={{
                        width: `${animatedLatestScore}%`,
                        height: "100%",
                        borderRadius: "9999px",
                        backgroundColor:
                          latestExactScore >= 70 ? "var(--accent-emerald)" : latestExactScore >= 50 ? "var(--accent-brand)" : "var(--accent-amber)"
                      }}
                    />
                  </div>
                )}

                {hasCompletedInterview && latestCompletedSession?.mode && (
                  <div
                    style={{
                      fontSize: "0.7rem",
                      fontWeight: 600,
                      color: "var(--text-tertiary)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      marginBottom: "0.35rem"
                    }}
                  >
                    {latestCompletedSession.mode} interview
                  </div>
                )}

                {/* Time Ago */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  <Clock size={12} />
                  <span>{hasCompletedInterview ? `Completed ${latestTimeAgo}` : "Start your first session"}</span>
                </div>
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              {hasCompletedInterview ? (
                <Link
                  href={`/reports/${latestCompletedSession.id}`}
                  style={{
                    color: "var(--accent-brand)",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    textDecoration: "none",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem"
                  }}
                >
                  <span>View Report</span>
                  <ArrowRight size={13} />
                </Link>
              ) : (
                <button
                  onClick={() => openInterviewModal()}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--accent-brand)",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
                    padding: 0
                  }}
                >
                  <span>Start Interview</span>
                  <ArrowRight size={13} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Motivation / Progress Card */}
        <div
          className="glass-card hover-elevate rise-in"
          style={{
            animationDelay: "300ms",
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "18px",
            boxShadow: "0 1px 0 rgba(255, 255, 255, 0.05) inset, 0 20px 48px -22px rgba(0, 0, 0, 0.88)",
            padding: "1.15rem 1.75rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            position: "relative",
            overflow: "hidden",
            zIndex: 1
          }}
        >
          {/* Left Text with Lightbulb */}
          <div style={{ display: "flex", alignItems: "center", gap: "1.1rem" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "12px",
                backgroundColor: "var(--accent-brand-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                color: "var(--accent-brand)"
              }}
            >
              <Lightbulb size={22} strokeWidth={2} />
            </div>
            <div>
              <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.15rem" }}>
                Keep going, {firstName}! 🚀
              </div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Consistency today, selection tomorrow.
              </div>
            </div>
          </div>

          {/* Right Side: real score trend across completed interviews. Rendered
              only when at least two scored interviews exist — no invented curve. */}
          <div style={{ width: "260px", height: "58px", position: "relative" }} className="feature-graphic-desktop">
            {scoreTrend.length >= 2 ? (
              <>
                <svg width="100%" height="46" viewBox="0 0 260 46" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label={`Average score across your last ${scoreTrend.length} completed interviews`}>
                  <defs>
                    <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {(() => {
                    const pts = scoreTrend.map((score, i) => {
                      const x = scoreTrend.length === 1 ? 130 : 8 + (i * 244) / (scoreTrend.length - 1);
                      const y = 40 - (Math.min(100, Math.max(0, score)) / 100) * 34;
                      return { x, y, score };
                    });
                    const line = pts.map((pt, i) => `${i === 0 ? "M" : "L"} ${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(" ");
                    const area = `${line} L ${pts[pts.length - 1].x.toFixed(1)},46 L ${pts[0].x.toFixed(1)},46 Z`;
                    return (
                      <>
                        <path d={area} fill="url(#chartGradient)" />
                        <path d={line} stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                        {pts.map((pt, i) => (
                          <circle
                            key={i}
                            cx={pt.x}
                            cy={pt.y}
                            r={i === pts.length - 1 ? 4 : 3}
                            fill={i === pts.length - 1 ? "#a79bff" : "#12142a"}
                            stroke={i === pts.length - 1 ? "#12142a" : "#8b7dff"}
                            strokeWidth="2"
                          >
                            <title>{`Interview ${i + 1}: ${pt.score}/100`}</title>
                          </circle>
                        ))}
                      </>
                    );
                  })()}
                </svg>
                <div style={{ fontSize: "0.68rem", color: "var(--text-tertiary)", textAlign: "right", fontWeight: 600 }}>
                  Score across {scoreTrend.length} completed interviews
                </div>
              </>
            ) : (
              <div
                style={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-end",
                  justifyContent: "center",
                  gap: "0.3rem",
                  textAlign: "right"
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: "26px" }} aria-hidden="true">
                  {[10, 16, 12, 20, 14].map((h, i) => (
                    <span key={i} style={{ width: "5px", height: `${h}px`, borderRadius: "3px", backgroundColor: "var(--accent-brand-light)" }} />
                  ))}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)", fontWeight: 500, maxWidth: "230px" }}>
                  {scoreTrend.length === 1
                    ? "One more interview and your score trend appears here."
                    : "Complete interviews to build your score trend."}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Resume upload progress — reflects the existing upload state machine */}
      {uploadStatus !== "IDLE" && (
        <div
          role="status"
          aria-live="polite"
          className="fade-in"
          style={{
            position: "fixed",
            right: "1.5rem",
            bottom: "1.5rem",
            zIndex: 1100,
            maxWidth: "340px",
            display: "flex",
            alignItems: "flex-start",
            gap: "0.65rem",
            padding: "0.85rem 1rem",
            borderRadius: "12px",
            backgroundColor: "var(--bg-surface)",
            border: `1px solid ${uploadStatus === "FAILED" ? "rgba(251, 113, 133, 0.32)" : uploadStatus === "READY" ? "rgba(52, 211, 153, 0.32)" : "var(--border-subtle)"}`,
            backdropFilter: "blur(20px) saturate(150%)",
            WebkitBackdropFilter: "blur(20px) saturate(150%)",
            boxShadow: "var(--shadow-modal)"
          }}
        >
          <div style={{ flexShrink: 0, marginTop: "1px" }}>
            {uploadStatus === "FAILED" ? (
              <AlertCircle size={17} color="var(--accent-rose)" />
            ) : uploadStatus === "READY" ? (
              <CheckCircle2 size={17} color="var(--accent-emerald)" />
            ) : (
              <Sparkles size={17} color="var(--accent-brand)" />
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.25rem" }}>
              {uploadStatus === "FAILED" ? "Resume upload failed" : uploadStatus === "READY" ? "Resume ready" : "Processing resume"}
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", lineHeight: 1.45 }}>
              {uploadStatus === "FAILED" ? uploadError : statusMessage}
            </div>
            {uploadStatus !== "FAILED" && uploadStatus !== "READY" && (
              <div
                className="indeterminate-track"
                aria-hidden="true"
                style={{ marginTop: "0.55rem", height: "4px", borderRadius: "9999px", color: "var(--accent-brand)" }}
              />
            )}
          </div>
          {uploadStatus === "FAILED" && (
            <button
              onClick={() => setUploadStatus("IDLE")}
              aria-label="Dismiss"
              style={{ background: "transparent", border: "none", color: "var(--text-tertiary)", cursor: "pointer", padding: 0 }}
            >
              <X size={15} />
            </button>
          )}
        </div>
      )}

      {/* Replace Resume Modal */}
      {showReplaceModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(4, 5, 11, 0.72)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "1rem"
          }}
          onClick={() => setShowReplaceModal(false)}
        >
          <div
            style={{
              maxWidth: "420px",
              width: "100%",
              padding: "1.75rem",
              backgroundColor: "var(--bg-surface)",
              borderRadius: "14px",
              backdropFilter: "blur(24px) saturate(150%)",
              WebkitBackdropFilter: "blur(24px) saturate(150%)",
              boxShadow: "var(--shadow-modal)",
              position: "relative",
              border: "1px solid var(--border-subtle)"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600, color: "var(--text-primary)" }}>Replace current resume?</h3>
              <button
                onClick={() => setShowReplaceModal(false)}
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0.2rem" }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1.5rem", lineHeight: 1.5 }}>
              Your new resume will be parsed to update your extracted skills and calculate new role compatibility recommendations.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button onClick={() => setShowReplaceModal(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowReplaceModal(false);
                  fileInputRef.current?.click();
                }}
                className="btn btn-primary"
              >
                <Upload size={14} /> <span>Choose Resume</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interview Mode Modal */}
      {showModeModal && selectedRole && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(4, 5, 11, 0.72)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "1rem"
          }}
          onClick={() => setShowModeModal(false)}
        >
          <div
            style={{
              maxWidth: "460px",
              width: "100%",
              padding: "1.75rem",
              backgroundColor: "var(--bg-surface)",
              borderRadius: "14px",
              backdropFilter: "blur(24px) saturate(150%)",
              WebkitBackdropFilter: "blur(24px) saturate(150%)",
              boxShadow: "var(--shadow-modal)",
              position: "relative",
              border: "1px solid var(--border-subtle)"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600, color: "var(--text-primary)" }}>Select Interview Format</h3>
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  Role: <strong style={{ color: "var(--text-primary)" }}>{selectedRole.title}</strong>
                </span>
              </div>
              <button
                onClick={() => setShowModeModal(false)}
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0.2rem" }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            {highestMatch && highestMatch.is_eligible === false ? (
              <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "var(--accent-amber-light)", border: "1px solid rgba(251, 191, 36, 0.32)", borderRadius: "10px", color: "var(--accent-amber)" }}>
                <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "0.3rem" }}>
                  Your profile needs a little more information
                </div>
                <p style={{ fontSize: "0.825rem", color: "var(--accent-amber)", margin: "0 0 0.8rem 0", lineHeight: 1.45 }}>
                  To create a meaningful role-specific interview, we need more evidence from your resume. Add a few technical skills, projects, or relevant experience and try again.
                </p>
                <Link
                  href="/resume"
                  onClick={() => setShowModeModal(false)}
                  className="btn btn-primary"
                  style={{ fontSize: "0.8rem", padding: "0.45rem 1rem", backgroundColor: "var(--accent-amber)", color: "#ffffff", display: "inline-flex", gap: "0.35rem" }}
                >
                  <Upload size={13} /> <span>Update Resume / Profile</span>
                </Link>
              </div>
            ) : (

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1.25rem" }}>
              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=text`}
                className="format-option-card"
                style={{
                  padding: "1rem 1.15rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.9rem",
                  textDecoration: "none",
                  backgroundColor: "var(--bg-surface)",
                  borderRadius: "12px",
                  border: "1px solid var(--border-subtle)"
                }}
              >
                <div style={{ backgroundColor: "var(--bg-subtle)", padding: "0.65rem", borderRadius: "10px", color: "var(--text-primary)", border: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <MessageSquare size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>Text Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>Conversational technical interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="var(--text-muted)" />
                </div>
              </Link>

              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=audio`}
                className="format-option-card"
                style={{
                  padding: "1rem 1.15rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.9rem",
                  textDecoration: "none",
                  backgroundColor: "var(--bg-surface)",
                  borderRadius: "12px",
                  border: "1px solid var(--border-subtle)"
                }}
              >
                <div style={{ backgroundColor: "var(--accent-brand-light)", padding: "0.65rem", borderRadius: "10px", color: "#c084fc", border: "1px solid rgba(192, 132, 252, 0.28)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Mic size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>Voice Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>Real-time spoken interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="var(--text-muted)" />
                </div>
              </Link>

              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=video`}
                className="format-option-card"
                style={{
                  padding: "1rem 1.15rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.9rem",
                  textDecoration: "none",
                  backgroundColor: "var(--bg-surface)",
                  borderRadius: "12px",
                  border: "1px solid var(--border-subtle)"
                }}
              >
                <div style={{ backgroundColor: "var(--accent-brand-light)", padding: "0.65rem", borderRadius: "10px", color: "var(--accent-brand)", border: "1px solid rgba(139, 125, 255, 0.28)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Video size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>Video Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>AI video interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="var(--text-muted)" />
                </div>
              </Link>
            </div>
            )}
          </div>
        </div>
      )}

      <style jsx global>{`
        .hover-lift {
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .hover-lift:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .format-option-card {
          transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .format-option-card:hover {
          border-color: #6366f1 !important;
          background-color: #fafafa !important;
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(99, 102, 241, 0.08);
        }
        .format-option-card:hover .format-arrow {
          transform: translateX(3px);
          transition: transform 0.18s ease;
        }
        @media (max-width: 900px) {
          .feature-graphic-desktop {
            display: none !important;
          }
        }
      `}</style>
    </WorkspaceLayout>
  );
}
