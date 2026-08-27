"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { getStoredToken, requireAuth } from "@/lib/auth";
import { ResumeItem, JobMatchResult } from "@/types";
import {
  FileText,
  Upload,
  CheckCircle2,
  Sparkles,
  Edit3,
  Save,
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  GraduationCap,
  Briefcase,
  Play,
  X,
  Code2
} from "lucide-react";

export default function ResumeIntelligencePage() {
  const router = useRouter();
  const [currentResume, setCurrentResume] = useState<ResumeItem | null>(null);
  const [matches, setMatches] = useState<JobMatchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadStatus, setUploadStatus] = useState<"IDLE" | "UPLOADING" | "PROCESSING" | "EXTRACTING" | "READY" | "FAILED">("IDLE");
  const [statusMessage, setStatusMessage] = useState("");
  const [editSkills, setEditSkills] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (requireAuth(router)) {
      loadResumeData();
    }
  }, []);

  async function loadResumeData() {
    setLoading(true);
    setErrorMessage("");
    try {
      const [currData, matchData]: [any, any] = await Promise.all([
        apiRequest("/resume/current").catch(() => null),
        apiRequest("/jobs/matches").catch(() => [])
      ]);
      setCurrentResume(currData || null);
      setMatches(matchData || []);
      if (currData && currData.resume_profile) {
        setEditSkills(currData.resume_profile.skills?.join(", ") || "");
      }
    } catch (err) {
      console.error("Resume data fetch error:", err);
    } finally {
      setLoading(false);
    }
  }

  const handleUpload = async (file: File) => {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage("File exceeds the maximum allowed size of 10 MB.");
      return;
    }

    setErrorMessage("");
    setUploadStatus("UPLOADING");
    setStatusMessage("Uploading resume document...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const token = getStoredToken();
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      setTimeout(() => {
        setUploadStatus("PROCESSING");
        setStatusMessage("Parsing document & extracting text...");
      }, 400);

      setTimeout(() => {
        setUploadStatus("EXTRACTING");
        setStatusMessage("Normalizing skills & structuring profile...");
      }, 1000);

      const res = await fetch(`${API_BASE_URL}/resume/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) {
        setUploadStatus("READY");
        setStatusMessage("Resume parsed and saved successfully!");
        setShowReplaceModal(false);
        await loadResumeData();
        setTimeout(() => {
          setUploadStatus("IDLE");
          setStatusMessage("");
        }, 1500);
      } else {
        const errData = await res.json().catch(() => ({}));
        setUploadStatus("FAILED");
        setErrorMessage(errData.detail || "Resume upload failed. Please verify format and size.");
      }
    } catch (err: any) {
      setUploadStatus("FAILED");
      setErrorMessage(err.message || "Error uploading resume file.");
    }
  };

  const handleSaveEditedSkills = async (resumeId: number) => {
    try {
      const skillsArray = editSkills
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      await apiRequest(`/resume/${resumeId}/profile`, {
        method: "PUT",
        body: JSON.stringify({
          skills: skillsArray,
          technologies: skillsArray
        })
      });
      await loadResumeData();
      setIsEditing(false);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update extracted skills.");
    }
  };

  const profile = currentResume?.resume_profile;
  const educationList = profile?.education || [];
  const projectsList = profile?.projects || [];
  const experienceList = profile?.experience || [];

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      <Navbar />

      {/* Hidden input */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".pdf,.docx,.txt"
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
            e.target.value = "";
          }
        }}
      />

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Breadcrumb Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.75rem", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <Link href="/dashboard" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", color: "#4f46e5", textDecoration: "none", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.4rem" }}>
              <ArrowLeft size={16} /> Back to Dashboard
            </Link>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.03em" }}>
              Resume Analysis & Intelligence
            </h1>
            <p style={{ color: "#64748b", fontSize: "0.9rem" }}>
              Detailed breakdown of extracted skills, education history, and role matches powering your interview preparation.
            </p>
          </div>

          <div style={{ display: "flex", gap: "0.6rem" }}>
            <button onClick={() => setShowReplaceModal(true)} className="btn btn-secondary" style={{ padding: "0.6rem 1rem" }}>
              <RefreshCw size={15} /> Replace Resume
            </button>
            <Link href="/interview/configure" className="btn btn-primary" style={{ padding: "0.6rem 1.15rem" }}>
              <Play size={15} /> Practice Interview
            </Link>
          </div>
        </div>

        {errorMessage && (
          <div style={{ padding: "0.75rem 1.25rem", backgroundColor: "#fff1f2", border: "1px solid #fecdd3", borderRadius: "10px", color: "#be123c", fontSize: "0.88rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <AlertCircle size={16} /> {errorMessage}
          </div>
        )}

        {savedSuccess && (
          <div style={{ padding: "0.75rem 1.25rem", backgroundColor: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "10px", color: "#047857", fontSize: "0.88rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <CheckCircle2 size={16} /> Extracted resume data updated and persisted in database!
          </div>
        )}

        {/* Processing Indicator */}
        {uploadStatus !== "IDLE" && (
          <div className="saas-card" style={{ padding: "1.25rem", backgroundColor: "#ffffff", borderRadius: "12px", border: "1px solid #e2e8f0", marginBottom: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem", color: "#4f46e5", fontSize: "0.88rem" }}>
              <RefreshCw size={15} className="spin" />
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
        )}

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <div className="saas-card skeleton" style={{ height: "100px" }} />
            <div className="saas-card skeleton" style={{ height: "140px" }} />
            <div className="saas-card skeleton" style={{ height: "180px" }} />
          </div>
        ) : !currentResume ? (
          /* Empty State */
          <div className="saas-card" style={{ padding: "3.5rem 2rem", textAlign: "center", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <FileText size={44} color="#94a3b8" style={{ marginBottom: "0.75rem" }} />
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.35rem" }}>No Resume Uploaded</h2>
            <p style={{ color: "#64748b", maxWidth: "460px", margin: "0 auto 1.25rem", fontSize: "0.9rem" }}>
              Upload your resume (PDF, DOCX, TXT) to extract verified skills, education history, and matching job roles.
            </p>
            <button onClick={() => fileInputRef.current?.click()} className="btn btn-primary">
              <Upload size={16} /> Choose Resume File
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {/* Section 1: Resume Overview */}
            <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
                <div>
                  <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>Resume Overview</span>
                  <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#0f172a", margin: "0.25rem 0" }}>{currentResume.filename}</h2>
                  <div style={{ display: "flex", gap: "1.25rem", color: "#64748b", fontSize: "0.85rem", marginTop: "0.3rem", flexWrap: "wrap" }}>
                    <span>Uploaded: {new Date(currentResume.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</span>
                    <span>File size: {(currentResume.file_size / 1024).toFixed(1)} KB</span>
                    <span style={{ color: "#059669", fontWeight: 600 }}>✓ Processed successfully</span>
                  </div>
                </div>
                <button onClick={() => setShowReplaceModal(true)} className="btn btn-secondary" style={{ padding: "0.45rem 0.85rem", fontSize: "0.82rem" }}>
                  <RefreshCw size={13} /> Replace
                </button>
              </div>
            </div>

            {/* Section 2: Skills with Edit Mode */}
            <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
                <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <Code2 size={18} color="#4f46e5" /> Extracted Technologies & Skills ({profile?.skills?.length || 0})
                </h3>
                <button onClick={() => setIsEditing(!isEditing)} className="btn btn-secondary" style={{ padding: "0.3rem 0.7rem", fontSize: "0.78rem" }}>
                  <Edit3 size={13} /> {isEditing ? "Cancel" : "Edit Skills"}
                </button>
              </div>

              {isEditing ? (
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#64748b", marginBottom: "0.35rem" }}>
                    Edit Skills (comma-separated):
                  </label>
                  <input
                    type="text"
                    value={editSkills}
                    onChange={(e) => setEditSkills(e.target.value)}
                    className="form-input"
                    style={{ marginBottom: "0.65rem" }}
                  />
                  <button onClick={() => handleSaveEditedSkills(currentResume.id)} className="btn btn-primary" style={{ padding: "0.45rem 0.9rem", fontSize: "0.82rem" }}>
                    <Save size={14} /> Save Corrected Skills
                  </button>
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                  {(!profile?.skills || profile.skills.length === 0) ? (
                    <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>No skills detected in resume.</span>
                  ) : (
                    profile.skills.map((s: string) => (
                      <span key={s} className="badge badge-primary" style={{ fontSize: "0.78rem", padding: "0.25rem 0.65rem" }}>
                        {s}
                      </span>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Section 3: Education & Projects / Experience Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.25rem" }}>
              {/* Education */}
              <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.85rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
                  <GraduationCap size={18} color="#4f46e5" /> Education
                </h3>
                {educationList.length === 0 ? (
                  <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: 0 }}>Not available in resume</p>
                ) : (
                  educationList.map((edu: any, idx: number) => (
                    <div key={idx} style={{ padding: "0.65rem 0.85rem", backgroundColor: "#f8fafc", border: "1px solid #f1f5f9", borderRadius: "10px", marginBottom: "0.5rem", fontSize: "0.88rem" }}>
                      <strong style={{ color: "#0f172a" }}>{edu.degree || "Degree not specified"}</strong>
                      <div style={{ color: "#64748b", fontSize: "0.8rem", marginTop: "0.15rem" }}>
                        {edu.institution || "Institution not specified"} {edu.year ? `• ${edu.year}` : ""}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Projects & Experience */}
              <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.85rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
                  <Briefcase size={18} color="#0284c7" /> Projects & Experience
                </h3>
                {projectsList.length === 0 && experienceList.length === 0 ? (
                  <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: 0 }}>Not available in resume</p>
                ) : (
                  <>
                    {experienceList.map((exp: any, idx: number) => (
                      <div key={`exp-${idx}`} style={{ padding: "0.65rem 0.85rem", backgroundColor: "#f8fafc", border: "1px solid #f1f5f9", borderRadius: "10px", marginBottom: "0.5rem", fontSize: "0.88rem" }}>
                        <strong style={{ color: "#0f172a" }}>{exp.role || "Role"}</strong> {exp.company ? `• ${exp.company}` : ""}
                        {exp.duration && <div style={{ color: "#94a3b8", fontSize: "0.78rem" }}>{exp.duration}</div>}
                      </div>
                    ))}
                    {projectsList.map((proj: any, idx: number) => (
                      <div key={`proj-${idx}`} style={{ padding: "0.65rem 0.85rem", backgroundColor: "#f8fafc", border: "1px solid #f1f5f9", borderRadius: "10px", marginBottom: "0.5rem", fontSize: "0.88rem" }}>
                        <strong style={{ color: "#0f172a" }}>{proj.title || "Project"}</strong>
                        {proj.description && <div style={{ color: "#64748b", fontSize: "0.8rem", marginTop: "0.15rem" }}>{proj.description}</div>}
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* Section 4: Recommended Roles */}
            {matches.length > 0 && (
              <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
                <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#0f172a", marginBottom: "0.85rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
                  <Sparkles size={18} color="#059669" /> Recommended Role Alignments
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
                  {matches.slice(0, 3).map((m) => (
                    <div key={m.role_id} style={{ padding: "1rem", backgroundColor: "#f8fafc", border: "1px solid #f1f5f9", borderRadius: "10px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                          <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 700, color: "#0f172a" }}>{m.role_title}</h4>
                          <span className="badge badge-success">{m.overall_score}%</span>
                        </div>
                        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>{m.company_name}</span>
                      </div>
                      <Link href={`/interview/configure?company_id=${m.company_id}&role_id=${m.role_id}`} className="btn btn-primary" style={{ marginTop: "0.85rem", padding: "0.45rem", fontSize: "0.8rem", justifyContent: "center" }}>
                        Practice Role
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Replace Resume Modal */}
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
              Your new resume will be processed and used for future recommendations and skill extraction.
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
    </div>
  );
}
