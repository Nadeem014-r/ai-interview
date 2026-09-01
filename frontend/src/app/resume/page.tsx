"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { getStoredToken, requireAuth } from "@/lib/auth";
import { ResumeItem, JobMatchResult } from "@/types";
import {
  FileText,
  Upload,
  CheckCircle2,
  Sparkles,
  Pencil,
  Save,
  AlertCircle,
  RefreshCw,
  GraduationCap,
  Briefcase,
  Play,
  X,
  Code2,
  User,
  FolderGit2
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
  const explicitFacts = profile?.explicit_facts || {};
  const modelInferred = profile?.model_inferred || {};

  const candidateName = explicitFacts?.candidate_name || null;
  const candidateDomain = modelInferred?.primary_technical_domain || null;
  const expLevel = modelInferred?.estimated_experience_level || null;

  return (
    <WorkspaceLayout sectionTitle="Resume Intelligence" sectionSubtitle="Extracted skills, credentials, and role alignments">
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

      {/* Header Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
            Resume Intelligence Workspace
          </h2>
          <span style={{ fontSize: "0.8rem", color: "#71717a" }}>
            Extracted facts powering personalized questions and role matches
          </span>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={() => setShowReplaceModal(true)} className="btn btn-secondary" style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}>
            <RefreshCw size={13} /> <span>Replace Resume</span>
          </button>
          <Link href="/interview/configure" className="btn btn-primary" style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}>
            <Play size={13} /> <span>Practice Interview</span>
          </Link>
        </div>
      </div>

      {errorMessage && (
        <div style={{ padding: "0.65rem 1rem", backgroundColor: "var(--accent-rose-light)", border: "1px solid #fecdd3", borderRadius: "8px", color: "var(--accent-rose)", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
          <AlertCircle size={15} /> {errorMessage}
        </div>
      )}

      {savedSuccess && (
        <div style={{ padding: "0.65rem 1rem", backgroundColor: "var(--accent-emerald-light)", border: "1px solid #a7f3d0", borderRadius: "8px", color: "var(--accent-emerald)", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
          <CheckCircle2 size={15} /> Extracted resume data updated and saved successfully!
        </div>
      )}

      {/* Processing Indicator */}
      {uploadStatus !== "IDLE" && (
        <div className="saas-card" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.45rem", color: "#09090b", fontSize: "0.85rem" }}>
            <RefreshCw size={14} className="spin" />
            <span style={{ fontWeight: 500 }}>{statusMessage}</span>
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
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="saas-card skeleton" style={{ height: "90px" }} />
          <div className="saas-card skeleton" style={{ height: "130px" }} />
          <div className="saas-card skeleton" style={{ height: "180px" }} />
        </div>
      ) : !currentResume ? (
        /* Empty State */
        <div className="saas-card" style={{ padding: "3rem 1.5rem", textAlign: "center" }}>
          <FileText size={36} color="#a1a1aa" style={{ marginBottom: "0.6rem" }} />
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#09090b", marginBottom: "0.3rem" }}>No Resume Uploaded</h3>
          <p style={{ color: "#71717a", maxWidth: "440px", margin: "0 auto 1.25rem", fontSize: "0.875rem" }}>
            Upload your resume (PDF, DOCX, TXT) to extract verified skills, education history, and matching job roles.
          </p>
          <button onClick={() => fileInputRef.current?.click()} className="btn btn-primary">
            <Upload size={15} /> <span>Choose Resume File</span>
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Section 1: Resume Overview & Profile Highlights */}
          <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.85rem" }}>
              <div>
                <span style={{ fontSize: "0.7rem", color: "#71717a", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
                  Resume Profile Overview
                </span>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 600, color: "#09090b", margin: "0.15rem 0" }}>
                  {candidateName ? `${candidateName} (${currentResume.filename})` : currentResume.filename}
                </h3>
                <div style={{ display: "flex", gap: "0.85rem", color: "#71717a", fontSize: "0.8rem", marginTop: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
                  {candidateDomain && (
                    <span className="badge badge-neutral" style={{ fontWeight: 600 }}>
                      {candidateDomain}
                    </span>
                  )}
                  {expLevel && (
                    <span className="badge badge-warning" style={{ textTransform: "capitalize" }}>
                      {expLevel} Level
                    </span>
                  )}
                  <span>Uploaded: {new Date(currentResume.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</span>
                  <span style={{ color: "var(--accent-emerald)", fontWeight: 500, display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <CheckCircle2 size={13} /> Parsed successfully
                  </span>
                </div>
              </div>
              <button onClick={() => setShowReplaceModal(true)} className="btn btn-secondary" style={{ padding: "0.35rem 0.75rem", fontSize: "0.78rem" }}>
                <RefreshCw size={13} /> <span>Replace</span>
              </button>
            </div>
          </div>

          {/* Section 2: Skills with Edit Mode */}
          <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <h3 style={{ margin: 0, fontSize: "0.95rem", fontWeight: 600, color: "#09090b", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                <Code2 size={16} /> Extracted Technologies & Skills ({profile?.skills?.length || 0})
              </h3>
              <button onClick={() => setIsEditing(!isEditing)} className="btn btn-secondary" style={{ padding: "0.25rem 0.6rem", fontSize: "0.75rem" }}>
                <Pencil size={12} /> <span>{isEditing ? "Cancel" : "Edit Skills"}</span>
              </button>
            </div>

            {isEditing ? (
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", color: "#71717a", marginBottom: "0.3rem" }}>
                  Edit Skills (comma-separated):
                </label>
                <input
                  type="text"
                  value={editSkills}
                  onChange={(e) => setEditSkills(e.target.value)}
                  className="form-input"
                  style={{ marginBottom: "0.65rem" }}
                />
                <button onClick={() => handleSaveEditedSkills(currentResume.id)} className="btn btn-primary" style={{ padding: "0.4rem 0.85rem", fontSize: "0.8rem" }}>
                  <Save size={13} /> <span>Save Corrected Skills</span>
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                {(!profile?.skills || profile.skills.length === 0) ? (
                  <span style={{ color: "#a1a1aa", fontSize: "0.825rem" }}>No skills detected in resume.</span>
                ) : (
                  profile.skills.map((s: string) => (
                    <span key={s} className="badge badge-neutral" style={{ fontSize: "0.75rem" }}>
                      {s}
                    </span>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Section 3: Education & Projects / Experience Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
            {/* Education */}
            <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <GraduationCap size={16} /> Education ({educationList.length})
              </h3>
              {educationList.length === 0 ? (
                <p style={{ color: "#a1a1aa", fontSize: "0.825rem", margin: 0 }}>Not available in resume</p>
              ) : (
                educationList.map((edu: any, idx: number) => (
                  <div key={idx} style={{ padding: "0.6rem 0.75rem", backgroundColor: "#fafafa", border: "1px solid #f4f4f5", borderRadius: "8px", marginBottom: "0.45rem", fontSize: "0.825rem" }}>
                    <strong style={{ color: "#09090b" }}>{edu.degree || "Degree"}</strong>
                    <div style={{ color: "#71717a", fontSize: "0.78rem", marginTop: "0.1rem" }}>
                      {edu.institution || "Institution"} {edu.year ? `• ${edu.year}` : ""}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Extracted Projects & Experience */}
            <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <FolderGit2 size={16} /> Extracted Projects & Experience ({projectsList.length + experienceList.length})
              </h3>
              {projectsList.length === 0 && experienceList.length === 0 ? (
                <p style={{ color: "#a1a1aa", fontSize: "0.825rem", margin: 0 }}>
                  No profile information or projects were identified in this resume.
                </p>
              ) : (
                <>
                  {projectsList.map((proj: any, idx: number) => {
                    const projectTitle = proj.name || proj.title || proj.heading || proj.project_name || "Project";
                    const technologies = proj.technologies && Array.isArray(proj.technologies) && proj.technologies.length > 0
                      ? proj.technologies.join(" • ")
                      : null;
                    const strengthScore = proj.score != null ? Math.round(proj.score) : null;
                    const evidenceSummary = proj.evidence_summary || (proj.description && proj.description !== projectTitle ? proj.description : null);

                    return (
                      <div key={`proj-${idx}`} style={{ padding: "0.65rem 0.85rem", backgroundColor: "#fafafa", border: "1px solid #f4f4f5", borderRadius: "8px", marginBottom: "0.5rem", fontSize: "0.825rem" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
                          <strong style={{ color: "#09090b" }}>{projectTitle}</strong>
                          <span className="badge badge-neutral" style={{ fontSize: "0.68rem" }}>Project</span>
                        </div>
                        {technologies && (
                          <div style={{ color: "#6366f1", fontSize: "0.76rem", fontWeight: 500, marginTop: "0.2rem" }}>
                            {technologies}
                          </div>
                        )}
                        {evidenceSummary && (
                          <div style={{ color: "#52525b", fontSize: "0.75rem", marginTop: "0.2rem", lineHeight: 1.35 }}>
                            {evidenceSummary}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {experienceList.map((exp: any, idx: number) => (
                    <div key={`exp-${idx}`} style={{ padding: "0.65rem 0.85rem", backgroundColor: "#fafafa", border: "1px solid #f4f4f5", borderRadius: "8px", marginBottom: "0.5rem", fontSize: "0.825rem" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
                        <strong style={{ color: "#09090b" }}>{exp.role || "Role"}</strong>
                        <span className="badge badge-neutral" style={{ fontSize: "0.68rem" }}>Experience</span>
                      </div>
                      {exp.company && (
                        <div style={{ color: "#71717a", fontSize: "0.78rem", marginTop: "0.15rem" }}>
                          {exp.company} {exp.duration ? `• ${exp.duration}` : ""}
                        </div>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          {/* Section 4: Recommended Roles */}
          {matches.length > 0 && (
            <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Sparkles size={16} /> Recommended Role Alignments
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "0.85rem" }}>
                {matches.slice(0, 3).map((m) => (
                  <div key={m.role_id} style={{ padding: "0.85rem", backgroundColor: "#fafafa", border: "1px solid #f4f4f5", borderRadius: "8px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                        <h4 style={{ margin: 0, fontSize: "0.9rem", fontWeight: 600, color: "#09090b" }}>{m.role_title}</h4>
                        <span className="badge badge-success">{m.overall_score}%</span>
                      </div>
                      <span style={{ fontSize: "0.78rem", color: "#71717a" }}>{m.company_name}</span>
                    </div>
                    <Link href={`/interview/configure?company_id=${m.company_id}&role_id=${m.role_id}`} className="btn btn-secondary" style={{ marginTop: "0.75rem", padding: "0.35rem", fontSize: "0.78rem", justifyContent: "center" }}>
                      <span>Practice Role</span>
                    </Link>
                  </div>
                ))}
              </div>
            </div>
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
              maxWidth: "440px",
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600, color: "#09090b" }}>Replace current resume?</h3>
              <button
                onClick={() => setShowReplaceModal(false)}
                style={{ background: "transparent", border: "none", color: "#71717a", cursor: "pointer", padding: "0.2rem" }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ color: "#71717a", fontSize: "0.875rem", marginBottom: "1.5rem", lineHeight: 1.5 }}>
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
                <Upload size={14} /> <span>Choose Resume File</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}
