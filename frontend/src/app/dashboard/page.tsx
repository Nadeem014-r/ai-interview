"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { getStoredToken, requireAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { InterviewSession, Company, JobMatchResult, ResumeItem, CandidateProfile } from "@/types";
import {
  Play,
  FileText,
  History,
  Building,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Upload,
  RefreshCw,
  ArrowRight,
  Code2,
  X,
  MessageSquare,
  Mic,
  Video
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();

  const [history, setHistory] = useState<InterviewSession[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [currentResume, setCurrentResume] = useState<ResumeItem | null>(null);
  const [candidateProfile, setCandidateProfile] = useState<CandidateProfile | null>(null);
  const [userName, setUserName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [errorState, setErrorState] = useState<string | null>(null);

  // Upload / Replace State Machine
  const [uploadStatus, setUploadStatus] = useState<"IDLE" | "UPLOADING" | "PROCESSING" | "EXTRACTING" | "READY" | "FAILED">("IDLE");
  const [statusMessage, setStatusMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
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
      setHistory(histData || []);
      setCompanies(compData || []);
      setMatches(matchData || []);
      setCurrentResume(currResumeData || null);
      setCandidateProfile(profData || null);
      if (userData && userData.full_name) {
        setUserName(userData.full_name);
      } else if (profData && profData.full_name) {
        setUserName(profData.full_name);
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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
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

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      <Navbar />

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem 1.5rem" }}>
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

        {/* Global Error Banner */}
        {errorState && (
          <div style={{
            padding: "0.85rem 1.25rem",
            backgroundColor: "#fff1f2",
            border: "1px solid #fecdd3",
            borderRadius: "12px",
            color: "#be123c",
            fontSize: "0.88rem",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <AlertCircle size={18} /> {errorState}
            </div>
            <button onClick={loadDashboardData} className="btn btn-secondary" style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}>
              Retry
            </button>
          </div>
        )}

        {/* ============================================================ */}
        {/* HERO SECTION: HERO HEADER + CALL TO ACTION                   */}
        {/* ============================================================ */}
        <div style={{ marginBottom: "1.75rem" }}>
          {loading ? (
            <div>
              <div className="skeleton" style={{ width: "380px", height: "36px", marginBottom: "0.5rem" }} />
              <div className="skeleton" style={{ width: "480px", height: "20px" }} />
            </div>
          ) : (
            <div>
              <h1 style={{ fontSize: "1.85rem", fontWeight: 800, color: "#0f172a", marginBottom: "0.25rem", letterSpacing: "-0.03em" }}>
                Ready for your interview, {displayName}?
              </h1>
              <p style={{ color: "#64748b", fontSize: "0.95rem" }}>
                Prepare smarter. Practice better. Choose how you want to conduct your interview practice.
              </p>
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* 3-COLUMN INTERVIEW ACTION CARDS (HERO CARDS)                 */}
        {/* ============================================================ */}
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
            {/* Text Interview Card */}
            <div className="saas-card" style={{
              padding: "1.75rem",
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
            }}>
              <div>
                <div style={{
                  backgroundColor: "#eef2ff",
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.25rem"
                }}>
                  <MessageSquare size={24} color="#4f46e5" />
                </div>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.4rem" }}>
                  Text Interview
                </h2>
                <p style={{ color: "#64748b", fontSize: "0.88rem", lineHeight: 1.5, marginBottom: "1.5rem" }}>
                  Practice through a conversational text-based interview with AI-powered instant rubric feedback.
                </p>
              </div>
              <button
                onClick={() => {
                  const role = matches.length > 0 ? { companyId: matches[0].company_id, roleId: matches[0].role_id } : { companyId: 1, roleId: 1 };
                  window.location.href = `/interview/configure?company_id=${role.companyId}&role_id=${role.roleId}&mode=text`;
                }}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "0.75rem", fontSize: "0.92rem" }}
              >
                Start Text Interview <ArrowRight size={16} />
              </button>
            </div>

            {/* Voice Interview Card */}
            <div className="saas-card" style={{
              padding: "1.75rem",
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
            }}>
              <div>
                <div style={{
                  backgroundColor: "#e0f2fe",
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.25rem"
                }}>
                  <Mic size={24} color="#0284c7" />
                </div>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.4rem" }}>
                  Voice Interview
                </h2>
                <p style={{ color: "#64748b", fontSize: "0.88rem", lineHeight: 1.5, marginBottom: "1.5rem" }}>
                  Practice answering questions out loud with speech-to-text communication assessment.
                </p>
              </div>
              <button
                onClick={() => {
                  const role = matches.length > 0 ? { companyId: matches[0].company_id, roleId: matches[0].role_id } : { companyId: 1, roleId: 1 };
                  window.location.href = `/interview/configure?company_id=${role.companyId}&role_id=${role.roleId}&mode=audio`;
                }}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "0.75rem", fontSize: "0.92rem" }}
              >
                Start Voice Interview <ArrowRight size={16} />
              </button>
            </div>

            {/* Video Interview Card */}
            <div className="saas-card" style={{
              padding: "1.75rem",
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
            }}>
              <div>
                <div style={{
                  backgroundColor: "#ecfdf5",
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1.25rem"
                }}>
                  <Video size={24} color="#059669" />
                </div>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.4rem" }}>
                  Video Interview
                </h2>
                <p style={{ color: "#64748b", fontSize: "0.88rem", lineHeight: 1.5, marginBottom: "1.5rem" }}>
                  Practice a realistic interview simulation with camera, audio, and behavioral confidence analysis.
                </p>
              </div>
              <button
                onClick={() => {
                  const role = matches.length > 0 ? { companyId: matches[0].company_id, roleId: matches[0].role_id } : { companyId: 1, roleId: 1 };
                  window.location.href = `/interview/configure?company_id=${role.companyId}&role_id=${role.roleId}&mode=video`;
                }}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "0.75rem", fontSize: "0.92rem" }}
              >
                Start Video Interview <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* RESUME ONBOARDING & STATUS CARD                              */}
        {/* ============================================================ */}
        <div style={{ marginBottom: "2rem" }}>
          {loading ? (
            <div className="saas-card" style={{ padding: "2rem", backgroundColor: "#ffffff" }}>
              <div className="skeleton" style={{ width: "220px", height: "24px", marginBottom: "1rem" }} />
              <div className="skeleton" style={{ width: "100%", height: "70px", marginBottom: "1rem" }} />
              <div className="skeleton" style={{ width: "160px", height: "36px" }} />
            </div>
          ) : !hasResume ? (
            /* STATE A: NO RESUME YET */
            <div
              className={`saas-card ${isDragOver ? "dropzone-active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              style={{
                padding: "2.5rem 2rem",
                backgroundColor: "#ffffff",
                border: "2px dashed #cbd5e1",
                borderRadius: "14px",
                textAlign: "center"
              }}
            >
              <div
                style={{
                  backgroundColor: "#eef2ff",
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: "1rem"
                }}
              >
                <Upload size={26} color="#4f46e5" />
              </div>
              <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.35rem" }}>
                Complete your profile
              </h2>
              <p style={{ color: "#64748b", fontSize: "0.9rem", maxWidth: "580px", margin: "0 auto 1.25rem" }}>
                Upload your resume to unlock personalized skills, role matching, and tailored interview recommendations.
              </p>

              {uploadStatus !== "IDLE" && uploadStatus !== "FAILED" ? (
                <div style={{ padding: "1.25rem", backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", maxWidth: "440px", margin: "0 auto 1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", marginBottom: "0.6rem", color: "#4f46e5", fontSize: "0.9rem" }}>
                    <RefreshCw size={16} className="spin" />
                    <span style={{ fontWeight: 600 }}>{statusMessage}</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width:
                          uploadStatus === "UPLOADING"
                            ? "35%"
                            : uploadStatus === "PROCESSING"
                            ? "70%"
                            : uploadStatus === "EXTRACTING"
                            ? "90%"
                            : "100%"
                      }}
                    />
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-primary"
                    style={{ padding: "0.75rem 2rem", fontSize: "0.95rem" }}
                  >
                    <Upload size={16} /> Upload Resume
                  </button>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                    Supported formats: PDF, DOCX • Drag & drop supported
                  </span>
                </div>
              )}

              {uploadError && (
                <div
                  style={{
                    marginTop: "1rem",
                    padding: "0.6rem 1rem",
                    backgroundColor: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: "8px",
                    color: "#be123c",
                    fontSize: "0.85rem",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.4rem"
                  }}
                >
                  <AlertCircle size={15} /> {uploadError}
                </div>
              )}
            </div>
          ) : (
            /* STATE B: RESUME EXISTS */
            <div className="saas-card" style={{
              padding: "1.75rem",
              backgroundColor: "#ffffff",
              borderRadius: "14px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)"
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", borderBottom: "1px solid #f1f5f9", paddingBottom: "1.25rem", marginBottom: "1.25rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
                    <span className="badge badge-success" style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
                      <CheckCircle2 size={13} /> Resume ready
                    </span>
                    <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
                      Status: <strong style={{ color: "#059669" }}>Processed successfully</strong>
                    </span>
                  </div>
                  <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#0f172a", margin: "0.2rem 0" }}>
                    {currentResume.filename}
                  </h2>
                  <span style={{ fontSize: "0.82rem", color: "#64748b" }}>
                    Last updated: {new Date(currentResume.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                  <Link href="/resume" className="btn btn-secondary" style={{ padding: "0.55rem 0.95rem", fontSize: "0.85rem" }}>
                    <FileText size={15} /> View Resume Analysis
                  </Link>
                  <button
                    onClick={() => setShowReplaceModal(true)}
                    className="btn btn-secondary"
                    style={{ padding: "0.55rem 0.95rem", fontSize: "0.85rem" }}
                  >
                    <RefreshCw size={15} /> Replace Resume
                  </button>
                </div>
              </div>

              {/* Uploading progress if replacing */}
              {uploadStatus !== "IDLE" && (
                <div style={{ padding: "0.9rem", backgroundColor: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", marginBottom: "1.25rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem", color: "#4f46e5", fontSize: "0.85rem" }}>
                    <RefreshCw size={15} className="spin" />
                    <span>{statusMessage}</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width:
                          uploadStatus === "UPLOADING"
                            ? "35%"
                            : uploadStatus === "PROCESSING"
                            ? "70%"
                            : uploadStatus === "EXTRACTING"
                            ? "90%"
                            : "100%"
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Extracted Skills Section */}
              <div>
                <h3 style={{ fontSize: "0.82rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "0.65rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                  <Code2 size={15} color="#4f46e5" /> Skills detected from your resume ({extractedSkills.length})
                </h3>
                {extractedSkills.length === 0 ? (
                  <p style={{ color: "#94a3b8", fontSize: "0.85rem" }}>No skills detected yet.</p>
                ) : (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                    {extractedSkills.map((skill: string) => (
                      <span key={skill} className="badge badge-primary" style={{ fontSize: "0.78rem", padding: "0.25rem 0.65rem" }}>
                        {skill}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* ROLE MATCHING & RECOMMENDATIONS SECTION                      */}
        {/* ============================================================ */}
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: "0.45rem" }}>
                <Sparkles size={18} color="#4f46e5" /> Recommended Roles
              </h2>
              <span style={{ fontSize: "0.82rem", color: "#64748b" }}>
                Role compatibility calculated from your extracted resume skills and profile
              </span>
            </div>
          </div>

          {loading ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
              <div className="saas-card skeleton" style={{ height: "200px" }} />
              <div className="saas-card skeleton" style={{ height: "200px" }} />
              <div className="saas-card skeleton" style={{ height: "200px" }} />
            </div>
          ) : matches.length === 0 ? (
            <div className="saas-card" style={{ padding: "2.5rem", textAlign: "center", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
              <Sparkles size={32} color="#94a3b8" style={{ marginBottom: "0.5rem" }} />
              <h3 style={{ fontSize: "1.05rem", color: "#0f172a" }}>No matching roles yet</h3>
              <p style={{ color: "#64748b", fontSize: "0.88rem", marginTop: "0.25rem" }}>
                Add or update your resume to receive personalized role recommendations.
              </p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
              {matches.slice(0, 3).map((m) => (
                <div key={m.role_id} className="saas-card" style={{
                  padding: "1.5rem",
                  backgroundColor: "#ffffff",
                  borderRadius: "14px",
                  border: "1px solid #e2e8f0",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                      <div>
                        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>{m.role_title}</h3>
                        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>{m.company_name} • {m.role_level}</span>
                      </div>
                      <span className="badge badge-success" style={{ fontSize: "0.82rem", fontWeight: 700 }}>
                        {m.overall_score}% Match
                      </span>
                    </div>

                    <div style={{ marginBottom: "0.75rem" }}>
                      <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block", marginBottom: "0.3rem" }}>
                        Why this role?
                      </span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
                        {m.matched_skills.length > 0 ? (
                          m.matched_skills.map((s) => (
                            <span key={s} className="badge badge-primary" style={{ fontSize: "0.72rem" }}>{s}</span>
                          ))
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>General profile alignment</span>
                        )}
                      </div>
                    </div>

                    {m.missing_skills.length > 0 && (
                      <div style={{ marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "0.75rem", color: "#be123c", textTransform: "uppercase", display: "block", marginBottom: "0.3rem" }}>
                          Skill Gaps:
                        </span>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
                          {m.missing_skills.slice(0, 3).map((s) => (
                            <span key={s} className="badge badge-warning" style={{ fontSize: "0.72rem" }}>{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => openInterviewModal({ companyId: m.company_id, roleId: m.role_id, title: m.role_title })}
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center", marginTop: "1rem", padding: "0.6rem" }}
                  >
                    <Play size={14} /> Prepare for Interview
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Target Companies Section */}
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>Target Placement Catalog</h2>
            <Link href="/companies" style={{ color: "#4f46e5", textDecoration: "none", fontSize: "0.88rem", fontWeight: 600 }}>
              View All Companies →
            </Link>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.25rem" }}>
            {companies.slice(0, 3).map((c) => (
              <div key={c.id} className="saas-card" style={{
                padding: "1.5rem",
                backgroundColor: "#ffffff",
                borderRadius: "14px",
                border: "1px solid #e2e8f0",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between"
              }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "0.65rem" }}>
                    <div style={{ backgroundColor: "#eef2ff", padding: "0.4rem", borderRadius: "8px", color: "#4f46e5" }}>
                      <Building size={20} />
                    </div>
                    <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>{c.name}</h3>
                  </div>
                  <p style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "1rem", lineHeight: 1.4 }}>{c.description}</p>
                </div>
                <Link href={`/companies/${c.id}/roles`} className="btn btn-secondary" style={{ width: "100%", justifyContent: "center" }}>
                  View Roles & Requirements
                </Link>
              </div>
            ))}
          </div>
        </div>

        {/* Recent History Table */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>Recent Interview Sessions</h2>
            <Link href="/history" style={{ color: "#4f46e5", textDecoration: "none", fontSize: "0.88rem", fontWeight: 600 }}>
              Full History →
            </Link>
          </div>

          {history.length === 0 ? (
            <div className="saas-card" style={{ textAlign: "center", padding: "2.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
              <History size={32} color="#94a3b8" style={{ marginBottom: "0.5rem" }} />
              <p style={{ color: "#64748b", marginBottom: "1rem", fontSize: "0.9rem" }}>Start your first practice interview.</p>
              <button onClick={() => openInterviewModal()} className="btn btn-primary">Launch Practice Session</button>
            </div>
          ) : (
            <div className="saas-card" style={{ overflowX: "auto", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.88rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #f1f5f9", color: "#64748b", backgroundColor: "#f8fafc" }}>
                    <th style={{ padding: "0.85rem 1rem" }}>Session ID</th>
                    <th style={{ padding: "0.85rem 1rem" }}>Target Role</th>
                    <th style={{ padding: "0.85rem 1rem" }}>Type & Mode</th>
                    <th style={{ padding: "0.85rem 1rem" }}>Status</th>
                    <th style={{ padding: "0.85rem 1rem" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 5).map((s) => (
                    <tr key={s.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "0.85rem 1rem", fontWeight: 600, color: "#0f172a" }}>#{s.id}</td>
                      <td style={{ padding: "0.85rem 1rem", color: "#334155" }}>{s.role_title || `Role #${s.role_id}`} ({s.company_name || "Company"})</td>
                      <td style={{ padding: "0.85rem 1rem", textTransform: "capitalize", color: "#64748b" }}>{s.interview_type || "Technical"} ({s.mode})</td>
                      <td style={{ padding: "0.85rem 1rem" }}>
                        <span className={`badge ${s.status === "completed" ? "badge-success" : "badge-warning"}`}>
                          {s.status}
                        </span>
                      </td>
                      <td style={{ padding: "0.85rem 1rem" }}>
                        {s.status === "completed" ? (
                          <Link href={`/reports/${s.id}`} className="btn btn-secondary" style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}>
                            <FileText size={13} /> View Report
                          </Link>
                        ) : (
                          <Link href={`/interview/${s.id}`} className="btn btn-primary" style={{ padding: "0.3rem 0.75rem", fontSize: "0.8rem" }}>
                            <Play size={13} /> Resume Session
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* ============================================================ */}
      {/* REPLACE RESUME CONFIRMATION MODAL                            */}
      {/* ============================================================ */}
      {showReplaceModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.5)",
            backdropFilter: "blur(4px)",
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
              maxWidth: "460px",
              width: "100%",
              padding: "2rem",
              backgroundColor: "#ffffff",
              borderRadius: "16px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
              position: "relative"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 700, color: "#0f172a" }}>Replace your current resume?</h3>
              <button
                onClick={() => setShowReplaceModal(false)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>

            <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: "1.5rem", lineHeight: 1.5 }}>
              Your new resume will be processed and used for future skills extraction and interview role recommendations.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                onClick={() => setShowReplaceModal(false)}
                className="btn btn-secondary"
                style={{ padding: "0.6rem 1.2rem" }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowReplaceModal(false);
                  fileInputRef.current?.click();
                }}
                className="btn btn-primary"
                style={{ padding: "0.6rem 1.2rem" }}
              >
                <Upload size={16} /> Choose Resume
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* INTERVIEW MODE SELECTION MODAL                               */}
      {/* ============================================================ */}
      {showModeModal && selectedRole && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.5)",
            backdropFilter: "blur(4px)",
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
              maxWidth: "500px",
              width: "100%",
              padding: "2rem",
              backgroundColor: "#ffffff",
              borderRadius: "16px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
              position: "relative"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "#0f172a" }}>Choose Interview Mode</h3>
                <span style={{ fontSize: "0.82rem", color: "#64748b" }}>
                  Target Role: <strong style={{ color: "#0f172a" }}>{selectedRole.title}</strong>
                </span>
              </div>
              <button
                onClick={() => setShowModeModal(false)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer" }}
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>

            <p style={{ color: "#64748b", fontSize: "0.88rem", marginBottom: "1.25rem" }}>
              Select how you would like to conduct your mock interview:
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {/* Text Interview */}
              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=text`}
                style={{
                  padding: "1rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.85rem",
                  textDecoration: "none",
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e2e8f0",
                  transition: "all 0.15s ease"
                }}
              >
                <div style={{ backgroundColor: "#eef2ff", padding: "0.6rem", borderRadius: "50%", color: "#4f46e5" }}>
                  <MessageSquare size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#0f172a" }}>Text Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>
                    Interactive chat-based technical & behavioral interview
                  </span>
                </div>
                <ArrowRight size={16} color="#94a3b8" />
              </Link>

              {/* Voice Interview */}
              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=audio`}
                style={{
                  padding: "1rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.85rem",
                  textDecoration: "none",
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e2e8f0",
                  transition: "all 0.15s ease"
                }}
              >
                <div style={{ backgroundColor: "#e0f2fe", padding: "0.6rem", borderRadius: "50%", color: "#0284c7" }}>
                  <Mic size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#0f172a" }}>Voice Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>
                    Real-time speech-to-text conversational interview
                  </span>
                </div>
                <ArrowRight size={16} color="#94a3b8" />
              </Link>

              {/* Video Interview */}
              <Link
                href={`/interview/configure?company_id=${selectedRole.companyId}&role_id=${selectedRole.roleId}&mode=video`}
                style={{
                  padding: "1rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.85rem",
                  textDecoration: "none",
                  backgroundColor: "#ffffff",
                  borderRadius: "12px",
                  border: "1px solid #e2e8f0",
                  transition: "all 0.15s ease"
                }}
              >
                <div style={{ backgroundColor: "#ecfdf5", padding: "0.6rem", borderRadius: "50%", color: "#059669" }}>
                  <Video size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#0f172a" }}>Video Interview</h4>
                  <span style={{ fontSize: "0.78rem", color: "#64748b" }}>
                    Full multimodal simulation with webcam & audio
                  </span>
                </div>
                <ArrowRight size={16} color="#94a3b8" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
