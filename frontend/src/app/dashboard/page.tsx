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

  // FIX #3: Derive interview readiness strictly from candidate resume & match analysis
  const highestMatch = matches.length > 0 ? matches[0] : null;

  const readinessScore = highestMatch ? Math.round(highestMatch.overall_score) : (hasResume ? 0 : null);
  const readinessLabel = readinessScore !== null ? (readinessScore >= 75 ? "Strong" : readinessScore >= 60 ? "Good" : readinessScore > 0 ? "Early Stage" : "Needs Preparation") : "Pending";

  // Real resume-derived breakdown scores (0% if no evidence exists)
  const techSkillScore = highestMatch?.breakdown?.skills_score != null ? Math.round(highestMatch.breakdown.skills_score) : 0;
  const projectsScore = highestMatch?.breakdown?.projects_score != null ? Math.round(highestMatch.breakdown.projects_score) : 0;
  const expScore = highestMatch?.breakdown?.experience_score != null ? Math.round(highestMatch.breakdown.experience_score) : 0;

  // Target role title & domain
  const targetRoleTitle = highestMatch?.role_title || candidateProfile?.target_role || "Software Engineer";
  const targetDomain = highestMatch?.role_title?.toLowerCase().includes("frontend")
    ? "Frontend"
    : highestMatch?.role_title?.toLowerCase().includes("full")
    ? "Full Stack"
    : "Backend";

  // FIX #2: Retrieve actual score from the most recent completed interview
  const latestCompletedSession = history.find((s) => s.status === "completed");
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
  
  // Format relative time helper
  const getTimeAgo = (dateString?: string) => {
    if (!dateString) return "Recently";
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHours < 1) return "Just now";
      if (diffHours < 24) return `${diffHours}h ago`;
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch {
      return "Recently";
    }
  };

  const latestTimeAgo = latestCompletedSession?.created_at ? getTimeAgo(latestCompletedSession.created_at) : (history[0]?.created_at ? getTimeAgo(history[0].created_at) : "Recently");

  // SVG Circular Gauge calculation
  const gaugeRadius = 52;
  const circumference = 2 * Math.PI * gaugeRadius;
  const strokeDashoffset = readinessScore !== null ? circumference - (readinessScore / 100) * circumference : circumference;

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
              border: "1px solid #fecdd3",
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
            <div style={{ fontSize: "0.925rem", fontWeight: 600, color: "#09090b", marginBottom: "0.4rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span>{getGreeting()}, {firstName}.</span> <span>👋</span>
            </div>
            <h1
              style={{
                fontSize: "2.35rem",
                fontWeight: 800,
                color: "#09090b",
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
              <span style={{ color: "#6366f1", position: "relative", display: "inline-flex", alignItems: "center" }}>
                next interview?
                <span
                  style={{
                    position: "absolute",
                    top: "-8px",
                    right: "-18px",
                    color: "#6366f1",
                    fontSize: "1.1rem",
                    lineHeight: 1
                  }}
                >
                  ✦
                </span>
              </span>
            </h1>
            <p style={{ color: "#71717a", fontSize: "0.875rem", margin: 0, maxWidth: "600px", lineHeight: 1.5 }}>
              Your interview preparation, resume intelligence, and placement progress — all in one place.
            </p>
          </div>

          {/* + New Interview CTA Button */}
          <button
            onClick={() => openInterviewModal()}
            style={{
              backgroundColor: "#09090b",
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
              boxShadow: "0 2px 8px rgba(9, 9, 11, 0.12)",
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
          style={{
            backgroundColor: "#ffffff",
            border: "1px solid #f1f1f4",
            borderRadius: "20px",
            boxShadow: "0 4px 20px -2px rgba(0, 0, 0, 0.03)",
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
                  background: "linear-gradient(180deg, #ede9fe 0%, #ddd6fe 100%)",
                  boxShadow: "0 2px 6px rgba(124, 58, 237, 0.15)"
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
                  color: "#09090b",
                  margin: "0 0 0.35rem 0",
                  letterSpacing: "-0.025em"
                }}
              >
                Start an AI Interview
              </h2>
              <p
                style={{
                  color: "#71717a",
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
                  backgroundColor: "#09090b",
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
                  boxShadow: "0 2px 6px rgba(0, 0, 0, 0.12)",
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
                backgroundColor: "#ffffff",
                borderRadius: "14px",
                border: "1px solid #eef2ff",
                boxShadow: "0 10px 25px -4px rgba(99, 102, 241, 0.12), 0 2px 6px rgba(0,0,0,0.03)",
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
                    backgroundColor: "#6366f1",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 2px 6px rgba(99, 102, 241, 0.3)"
                  }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
                  </svg>
                </div>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "3px" }}>
                  <div style={{ width: "24px", height: "4px", backgroundColor: "#6366f1", borderRadius: "2px" }} />
                  <div style={{ width: "16px", height: "3px", backgroundColor: "#e0e7ff", borderRadius: "2px" }} />
                </div>
              </div>

              {/* ID Lines */}
              <div style={{ display: "flex", flexDirection: "column", gap: "3.5px" }}>
                <div style={{ width: "100%", height: "4.5px", backgroundColor: "#f3f4f6", borderRadius: "3px" }} />
                <div style={{ width: "70%", height: "4.5px", backgroundColor: "#f3f4f6", borderRadius: "3px" }} />
              </div>
            </div>

            {/* Overlapping Waveform Card */}
            <div
              style={{
                position: "absolute",
                right: "-6px",
                width: "95px",
                height: "76px",
                backgroundColor: "#f5f3ff",
                borderRadius: "14px",
                border: "1px solid #ede9fe",
                boxShadow: "0 8px 20px -3px rgba(124, 58, 237, 0.12)",
                padding: "0.6rem 0.75rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "4px",
                transform: "rotate(6deg)",
                zIndex: 1
              }}
            >
              <div style={{ width: "3.5px", height: "14px", backgroundColor: "#818cf8", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "24px", backgroundColor: "#6366f1", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "34px", backgroundColor: "#7c3aed", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "20px", backgroundColor: "#6366f1", borderRadius: "2px" }} />
              <div style={{ width: "3.5px", height: "12px", backgroundColor: "#818cf8", borderRadius: "2px" }} />
            </div>

            {/* Subtle floating sparkles */}
            <div style={{ position: "absolute", top: "0px", right: "70px", color: "#818cf8", fontSize: "14px" }}>✦</div>
            <div style={{ position: "absolute", bottom: "-4px", left: "40px", color: "#c084fc", fontSize: "12px" }}>✦</div>
          </div>
        </div>

        {/* Four Insight Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1.15rem",
            marginBottom: "1.75rem",
            position: "relative",
            zIndex: 1
          }}
        >
          {/* Card 1: Interview Readiness (Derived from Resume & Profile Match) */}
          <div
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f1f4",
              borderRadius: "18px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.02)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", margin: 0 }}>
                  Interview Readiness
                </h3>
                <TrendingUp size={18} color="#6366f1" strokeWidth={2.2} />
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
                      stroke="#ede9fe"
                      strokeWidth="9"
                      fill="none"
                    />
                    {/* Progress Circle */}
                    <circle
                      cx="60"
                      cy="60"
                      r={gaugeRadius}
                      stroke="#6366f1"
                      strokeWidth="9"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                      fill="none"
                      style={{ transition: "stroke-dashoffset 0.8s ease-in-out" }}
                    />
                  </svg>
                  {/* Gauge Center Text */}
                  <div style={{ position: "absolute", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ fontSize: "1.65rem", fontWeight: 800, color: "#09090b", lineHeight: 1, letterSpacing: "-0.03em" }}>
                      {readinessScore !== null ? `${readinessScore}%` : "—"}
                    </span>
                    <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "#6366f1", marginTop: "3px" }}>
                      {readinessLabel}
                    </span>
                  </div>
                </div>
              </div>

              {/* Breakdown Bars (Derived from Resume Job Match Breakdown) */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", marginBottom: "0.5rem" }}>
                {/* Technical Skills */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "#71717a", width: "85px" }}>Technical Skills</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "#f3f4f6", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div style={{ width: `${techSkillScore}%`, height: "100%", backgroundColor: "#6366f1", borderRadius: "10px" }} />
                  </div>
                  <span style={{ fontWeight: 600, color: "#09090b", width: "28px", textAlign: "right" }}>{techSkillScore}%</span>
                </div>

                {/* Projects & Domain */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "#71717a", width: "85px" }}>Projects</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "#f3f4f6", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div style={{ width: `${projectsScore}%`, height: "100%", backgroundColor: "#6366f1", borderRadius: "10px" }} />
                  </div>
                  <span style={{ fontWeight: 600, color: "#09090b", width: "28px", textAlign: "right" }}>{projectsScore}%</span>
                </div>

                {/* Experience Match */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "#71717a", width: "85px" }}>Experience</span>
                  <div style={{ flex: 1, height: "5px", backgroundColor: "#f3f4f6", borderRadius: "10px", margin: "0 0.5rem", overflow: "hidden" }}>
                    <div style={{ width: `${expScore}%`, height: "100%", backgroundColor: "#6366f1", borderRadius: "10px" }} />
                  </div>
                  <span style={{ fontWeight: 600, color: "#09090b", width: "28px", textAlign: "right" }}>{expScore}%</span>
                </div>
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/resume"
                style={{
                  color: "#6366f1",
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
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f1f4",
              borderRadius: "18px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.02)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", margin: 0 }}>
                  Resume Status
                </h3>
                <FileCheck size={18} color="#2563eb" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "16px",
                    backgroundColor: "#eff6ff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "0.75rem",
                    boxShadow: "0 2px 8px rgba(37, 99, 235, 0.08)"
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
                    color: hasResume ? "#2563eb" : "#d97706",
                    fontSize: "0.9rem",
                    fontWeight: 700,
                    marginBottom: "0.45rem"
                  }}
                >
                  {hasResume ? <CheckCircle2 size={15} color="#2563eb" /> : <AlertCircle size={15} color="#d97706" />}
                  <span>{hasResume ? "Ready" : "Pending"}</span>
                </div>

                <div style={{ fontSize: "0.8rem", color: "#71717a", marginBottom: "0.25rem" }}>
                  {hasResume ? `${extractedSkills.length || 0} skills detected` : "Upload resume to extract skills"}
                </div>

                <div style={{ fontSize: "0.78rem", fontWeight: 500, color: "#09090b" }}>
                  {targetRoleTitle} • {targetDomain}
                </div>
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/resume"
                style={{
                  color: "#6366f1",
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
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f1f4",
              borderRadius: "18px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.02)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", margin: 0 }}>
                  Your Target
                </h3>
                <Target size={18} color="#10b981" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "50%",
                    backgroundColor: "#ecfdf5",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "0.75rem",
                    boxShadow: "0 2px 8px rgba(16, 185, 129, 0.08)"
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

                <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", marginBottom: "0.2rem" }}>
                  {targetRoleTitle}
                </div>

                <div style={{ fontSize: "0.8rem", color: "#71717a", marginBottom: "0.85rem" }}>
                  {targetDomain}
                </div>

                {/* Company Badges Row */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.55rem" }}>
                  {/* Google */}
                  <div
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "7px",
                      backgroundColor: "#ffffff",
                      border: "1px solid #e4e4e7",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
                    }}
                    title="Google"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.98 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                      />
                    </svg>
                  </div>

                  {/* Amazon */}
                  <div
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "7px",
                      backgroundColor: "#ffffff",
                      border: "1px solid #e4e4e7",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
                    }}
                    title="Amazon"
                  >
                    <span style={{ fontSize: "0.9rem", fontWeight: 800, color: "#111827", fontFamily: "sans-serif" }}>a</span>
                  </div>

                  {/* Microsoft */}
                  <div
                    style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "7px",
                      backgroundColor: "#ffffff",
                      border: "1px solid #e4e4e7",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
                    }}
                    title="Microsoft"
                  >
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 6px)", gap: "1.5px" }}>
                      <div style={{ width: "6px", height: "6px", backgroundColor: "#f25022" }} />
                      <div style={{ width: "6px", height: "6px", backgroundColor: "#7fba00" }} />
                      <div style={{ width: "6px", height: "6px", backgroundColor: "#00a4ef" }} />
                      <div style={{ width: "6px", height: "6px", backgroundColor: "#ffb900" }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Action Link */}
            <div style={{ paddingTop: "0.75rem", textAlign: "center" }}>
              <Link
                href="/companies"
                style={{
                  color: "#6366f1",
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
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #f1f1f4",
              borderRadius: "18px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.02)",
              padding: "1.35rem 1.4rem",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: "330px"
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", margin: 0 }}>
                  Latest Interview
                </h3>
                <AudioLines size={18} color="#6366f1" strokeWidth={2.2} />
              </div>

              {/* Center Graphic */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", margin: "0.75rem 0" }}>
                <div
                  style={{
                    width: "64px",
                    height: "64px",
                    borderRadius: "16px",
                    backgroundColor: "#f5f3ff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "3.5px",
                    marginBottom: "0.75rem",
                    boxShadow: "0 2px 8px rgba(99, 102, 241, 0.08)"
                  }}
                >
                  <div style={{ width: "3.5px", height: "12px", backgroundColor: "#818cf8", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "22px", backgroundColor: "#6366f1", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "30px", backgroundColor: "#7c3aed", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "18px", backgroundColor: "#6366f1", borderRadius: "2px" }} />
                  <div style={{ width: "3.5px", height: "10px", backgroundColor: "#818cf8", borderRadius: "2px" }} />
                </div>

                <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", marginBottom: "0.35rem" }}>
                  {hasCompletedInterview ? latestRoleTitle : "No interviews yet"}
                </div>

                {/* Score Pill Badge — FIX #2: Actual score from latest completed interview */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
                    backgroundColor: "#ede9fe",
                    color: "#6366f1",
                    padding: "0.22rem 0.65rem",
                    borderRadius: "20px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    marginBottom: "0.45rem"
                  }}
                >
                  {hasCompletedInterview && latestExactScore !== null ? (
                    <>
                      <CheckCircle2 size={12} strokeWidth={2.5} />
                      <span>{latestExactScore}/100</span>
                    </>
                  ) : hasCompletedInterview ? (
                    <span>Completed</span>
                  ) : (
                    <span>Pending Practice</span>
                  )}
                </div>

                {/* Time Ago */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.78rem", color: "#71717a" }}>
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
                    color: "#6366f1",
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
                    color: "#6366f1",
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
          style={{
            backgroundColor: "#ffffff",
            border: "1px solid #f1f1f4",
            borderRadius: "18px",
            boxShadow: "0 2px 10px rgba(0, 0, 0, 0.02)",
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
                backgroundColor: "#f5f3ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                color: "#6366f1"
              }}
            >
              <Lightbulb size={22} strokeWidth={2} />
            </div>
            <div>
              <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#09090b", marginBottom: "0.15rem" }}>
                Keep going, {firstName}! 🚀
              </div>
              <div style={{ fontSize: "0.82rem", color: "#71717a" }}>
                Consistency today, selection tomorrow.
              </div>
            </div>
          </div>

          {/* Right Side: Smooth Growth Spline Curve Graph */}
          <div style={{ width: "260px", height: "55px", position: "relative" }} className="feature-graphic-desktop">
            <svg width="100%" height="100%" viewBox="0 0 260 55" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* Area Fill */}
              <path
                d="M 10,48 Q 50,45 80,42 T 140,32 T 190,20 T 245,8 L 245,55 L 10,55 Z"
                fill="url(#chartGradient)"
              />
              {/* Trend Line */}
              <path
                d="M 10,48 Q 50,45 80,42 T 140,32 T 190,20 T 245,8"
                stroke="#6366f1"
                strokeWidth="2.5"
                strokeLinecap="round"
                fill="none"
              />
              {/* Nodes */}
              <circle cx="80" cy="42" r="3" fill="#ffffff" stroke="#6366f1" strokeWidth="2" />
              <circle cx="140" cy="32" r="3" fill="#ffffff" stroke="#6366f1" strokeWidth="2" />
              <circle cx="190" cy="20" r="3" fill="#ffffff" stroke="#6366f1" strokeWidth="2" />
              <circle cx="245" cy="8" r="4" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
            </svg>
          </div>
        </div>
      </div>

      {/* Replace Resume Modal */}
      {showReplaceModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(9, 9, 11, 0.4)",
            backdropFilter: "blur(4px)",
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
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              boxShadow: "var(--shadow-modal)",
              position: "relative",
              border: "1px solid #e4e4e7"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600, color: "#09090b" }}>Replace current resume?</h3>
              <button
                onClick={() => setShowReplaceModal(false)}
                style={{ background: "transparent", border: "none", color: "#71717a", cursor: "pointer", padding: "0.2rem" }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ color: "#71717a", fontSize: "0.85rem", marginBottom: "1.5rem", lineHeight: 1.5 }}>
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
            backgroundColor: "rgba(9, 9, 11, 0.4)",
            backdropFilter: "blur(4px)",
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
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              boxShadow: "var(--shadow-modal)",
              position: "relative",
              border: "1px solid #e4e4e7"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600, color: "#09090b" }}>Select Interview Format</h3>
                <span style={{ fontSize: "0.78rem", color: "#71717a" }}>
                  Role: <strong style={{ color: "#09090b" }}>{selectedRole.title}</strong>
                </span>
              </div>
              <button
                onClick={() => setShowModeModal(false)}
                style={{ background: "transparent", border: "none", color: "#71717a", cursor: "pointer", padding: "0.2rem" }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            {highestMatch && highestMatch.is_eligible === false ? (
              <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "#fffbeb", border: "1px solid #fde68a", borderRadius: "10px", color: "#92400e" }}>
                <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "0.3rem" }}>
                  Your profile needs a little more information
                </div>
                <p style={{ fontSize: "0.825rem", color: "#78350f", margin: "0 0 0.8rem 0", lineHeight: 1.45 }}>
                  To create a meaningful role-specific interview, we need more evidence from your resume. Add a few technical skills, projects, or relevant experience and try again.
                </p>
                <Link
                  href="/resume"
                  onClick={() => setShowModeModal(false)}
                  className="btn btn-primary"
                  style={{ fontSize: "0.8rem", padding: "0.45rem 1rem", backgroundColor: "#b45309", color: "#ffffff", display: "inline-flex", gap: "0.35rem" }}
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
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e4e4e7"
                }}
              >
                <div style={{ backgroundColor: "#f8fafc", padding: "0.65rem", borderRadius: "10px", color: "#09090b", border: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <MessageSquare size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b", letterSpacing: "-0.01em" }}>Text Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>Conversational technical interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="#94a3b8" />
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
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e4e4e7"
                }}
              >
                <div style={{ backgroundColor: "#faf5ff", padding: "0.65rem", borderRadius: "10px", color: "#7c3aed", border: "1px solid #f3e8ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Mic size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b", letterSpacing: "-0.01em" }}>Voice Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>Real-time spoken interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="#94a3b8" />
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
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e4e4e7"
                }}
              >
                <div style={{ backgroundColor: "#eef2ff", padding: "0.65rem", borderRadius: "10px", color: "#4f46e5", border: "1px solid #e0e7ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Video size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b", letterSpacing: "-0.01em" }}>Video Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>AI video interview</span>
                </div>
                <div className="format-arrow">
                  <ArrowRight size={16} color="#94a3b8" />
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
