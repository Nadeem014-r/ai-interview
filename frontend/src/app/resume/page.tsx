"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { ResumeItem } from "@/types";
import { FileText, Upload, CheckCircle, Sparkles, Edit3, Save, CheckCircle2, AlertCircle } from "lucide-react";

export default function ResumeIntelligencePage() {
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [editSkills, setEditSkills] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    loadResumes();
  }, []);

  async function loadResumes() {
    try {
      const data: any = await apiRequest("/resume");
      setResumes(data || []);
      if (data && data.length > 0 && data[0].resume_profile) {
        setEditSkills(data[0].resume_profile.skills?.join(", ") || "");
      }
    } catch (err) {
      console.error(err);
    }
  }

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    setUploading(true);
    setErrorMessage("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const token = getStoredToken();
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${API_BASE_URL}/resume/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (res.ok) {
        await loadResumes();
        setSelectedFile(null);
      } else {
        const errData = await res.json().catch(() => ({}));
        setErrorMessage(errData.detail || "Resume upload failed.");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Error uploading resume file.");
    } finally {
      setUploading(false);
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
      await loadResumes();
      setIsEditing(false);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to update extracted skills.");
    }
  };

  const activeResume = resumes[0];

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ marginBottom: "2rem" }}>
          <h2>Resume Intelligence Pipeline</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Extract explicit facts vs. model-inferred career intelligence, edit extracted data, and power grounded interview tailoring.
          </p>
        </div>

        {errorMessage && (
          <div style={{ padding: "0.75rem 1rem", background: "rgba(244, 63, 94, 0.15)", border: "1px solid rgba(244, 63, 94, 0.3)", borderRadius: "var(--radius-md)", color: "#fda4af", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <AlertCircle size={16} /> {errorMessage}
          </div>
        )}

        {savedSuccess && (
          <div style={{ padding: "0.75rem 1rem", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "var(--radius-md)", color: "#6ee7b7", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <CheckCircle2 size={16} /> Extracted resume data updated and persisted in database!
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "1.5rem" }}>
          {/* Upload Card */}
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <h4 style={{ marginBottom: "1rem" }}>Upload New Resume</h4>
            <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}
              />
              <button type="submit" disabled={!selectedFile || uploading} className="btn btn-primary" style={{ width: "100%" }}>
                <Upload size={16} /> {uploading ? "Extracting..." : "Upload & Parse"}
              </button>
            </form>

            <div style={{ marginTop: "2rem" }}>
              <h5 style={{ fontSize: "0.85rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.75rem" }}>Uploaded Resumes</h5>
              {resumes.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No resumes uploaded yet.</p>
              ) : (
                resumes.map((r) => (
                  <div key={r.id} style={{ padding: "0.6rem 0.8rem", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-md)", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                    <FileText size={14} style={{ marginRight: "0.4rem" }} /> {r.filename}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Intelligence Inspection Card */}
          <div>
            {!activeResume ? (
              <div className="glass-card" style={{ padding: "3rem", textAlign: "center" }}>
                <FileText size={40} color="var(--text-muted)" style={{ marginBottom: "1rem" }} />
                <p style={{ color: "var(--text-secondary)" }}>No resume uploaded yet. Upload a PDF, DOCX, or TXT file to extract skills and match jobs.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {/* Explicit Facts vs Inferred */}
                <div className="glass-card" style={{ padding: "1.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", color: "var(--accent-cyan)" }}>
                    <CheckCircle size={20} />
                    <h3 style={{ fontSize: "1.1rem" }}>Explicit Resume Facts (Verified from Text)</h3>
                  </div>
                  <pre style={{ background: "rgba(0,0,0,0.5)", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.85rem", fontFamily: "monospace", color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(activeResume.resume_profile?.explicit_facts || {}, null, 2)}
                  </pre>
                </div>

                <div className="glass-card" style={{ padding: "1.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", color: "var(--primary)" }}>
                    <Sparkles size={20} />
                    <h3 style={{ fontSize: "1.1rem" }}>Model-Inferred Career Context</h3>
                  </div>
                  <pre style={{ background: "rgba(0,0,0,0.5)", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.85rem", fontFamily: "monospace", color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(activeResume.resume_profile?.model_inferred || {}, null, 2)}
                  </pre>
                </div>

                {/* Extracted Skills Badges with Edit/Correct feature */}
                <div className="glass-card" style={{ padding: "1.5rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                    <h4 style={{ margin: 0 }}>Extracted Technologies & Skills</h4>
                    <button onClick={() => setIsEditing(!isEditing)} className="btn btn-secondary" style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem" }}>
                      <Edit3 size={14} /> {isEditing ? "Cancel" : "Edit Skills"}
                    </button>
                  </div>

                  {isEditing ? (
                    <div style={{ marginTop: "1rem" }}>
                      <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>
                        Edit Skills (comma-separated):
                      </label>
                      <input
                        type="text"
                        value={editSkills}
                        onChange={(e) => setEditSkills(e.target.value)}
                        className="form-input"
                        style={{ marginBottom: "0.75rem" }}
                      />
                      <button onClick={() => handleSaveEditedSkills(activeResume.id)} className="btn btn-primary" style={{ padding: "0.4rem 0.8rem", fontSize: "0.8rem" }}>
                        <Save size={14} /> Save Corrected Skills
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                      {(activeResume.resume_profile?.skills || []).length === 0 ? (
                        <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No skills identified in document.</span>
                      ) : (
                        (activeResume.resume_profile?.skills || []).map((s: string) => (
                          <span key={s} className="badge badge-primary">{s}</span>
                        ))
                      )}
                    </div>
                  )}
                </div>

                {/* Education and Experience Info */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
                  <div className="glass-card" style={{ padding: "1.5rem" }}>
                    <h4 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>Extracted Education</h4>
                    {(!activeResume.resume_profile?.education || activeResume.resume_profile.education.length === 0) ? (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>No explicit education entries extracted.</p>
                    ) : (
                      activeResume.resume_profile.education.map((edu: any, idx: number) => (
                        <div key={idx} style={{ padding: "0.5rem", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-md)", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                          <strong>{edu.degree || "Degree not specified"}</strong>
                          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{edu.institution || "Institution not specified"} {edu.year ? `(${edu.year})` : ""}</div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="glass-card" style={{ padding: "1.5rem" }}>
                    <h4 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>Extracted Experience / Projects</h4>
                    {((!activeResume.resume_profile?.experience || activeResume.resume_profile.experience.length === 0) &&
                      (!activeResume.resume_profile?.projects || activeResume.resume_profile.projects.length === 0)) ? (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>No explicit experience or projects listed.</p>
                    ) : (
                      <>
                        {activeResume.resume_profile?.experience?.map((exp: any, idx: number) => (
                          <div key={`exp-${idx}`} style={{ padding: "0.5rem", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-md)", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                            <strong>{exp.role || "Role"}</strong> - {exp.company || "Company"} ({exp.duration || "Duration"})
                          </div>
                        ))}
                        {activeResume.resume_profile?.projects?.map((proj: any, idx: number) => (
                          <div key={`proj-${idx}`} style={{ padding: "0.5rem", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-md)", marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                            <strong>{proj.title || "Project"}</strong>
                            <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>{proj.description}</div>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

