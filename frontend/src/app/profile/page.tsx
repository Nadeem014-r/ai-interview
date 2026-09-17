"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { CandidateProfile } from "@/types";
import { User, Save, CheckCircle2, AlertCircle } from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<CandidateProfile>({
    full_name: "",
    email: "",
    target_role: "",
    university: "",
    degree: "",
    graduation_year: undefined,
    skills: [],
    experience_years: undefined,
    bio: ""
  });
  const [skillsStr, setSkillsStr] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (requireAuth(router)) {
      loadProfile();
    }
  }, []);

  async function loadProfile() {
    try {
      const data: any = await apiRequest("/profile");
      if (data) {
        setProfile(data);
        if (data.skills) {
          setSkillsStr(data.skills.join(", "));
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg("");
    setErrorMsg("");

    // Rejected, never corrected: silently turning -0.5 into 0 would save a
    // number the candidate never entered. The backend enforces the same rule.
    const yearsValue =
      profile.experience_years === undefined || profile.experience_years === null
        ? undefined
        : Number(profile.experience_years);
    if (yearsValue !== undefined && (Number.isNaN(yearsValue) || yearsValue < 0)) {
      setErrorMsg("Years of experience cannot be negative. Enter 0 or more.");
      return;
    }

    setSaving(true);

    try {
      const skillsArray = skillsStr
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      const payload = {
        ...profile,
        skills: skillsArray,
        graduation_year: profile.graduation_year ? Number(profile.graduation_year) : undefined,
        // Sent as-is: `0` is a valid answer and a truthiness check used to drop it.
        experience_years: yearsValue
      };

      await apiRequest("/profile", {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      setSuccessMsg("Candidate profile settings saved successfully.");
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update profile settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <WorkspaceLayout sectionTitle="Settings" sectionSubtitle="Personal, academic, and interview preparation preferences">
      <div style={{ maxWidth: "800px" }}>
        <div style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>
            Account & Placement Profile Settings
          </h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.2rem" }}>
            Update your academic background and preferred engineering domains to improve question tailoring.
          </p>
        </div>

        {successMsg && (
          <div style={{ padding: "0.65rem 1rem", backgroundColor: "var(--accent-emerald-light)", border: "1px solid rgba(52, 211, 153, 0.32)", borderRadius: "8px", color: "var(--accent-emerald)", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <CheckCircle2 size={15} /> {successMsg}
          </div>
        )}

        {errorMsg && (
          <div style={{ padding: "0.65rem 1rem", backgroundColor: "var(--accent-rose-light)", border: "1px solid rgba(251, 113, 133, 0.32)", borderRadius: "8px", color: "var(--accent-rose)", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <AlertCircle size={15} /> {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Personal Information */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
              Personal Details
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Full Name</label>
                <input
                  type="text"
                  required
                  value={profile.full_name || ""}
                  onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                  className="form-input"
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Email Address</label>
                <input
                  type="email"
                  disabled
                  value={profile.email || ""}
                  className="form-input"
                  style={{ backgroundColor: "var(--bg-subtle)", cursor: "not-allowed" }}
                />
              </div>
            </div>
          </div>

          {/* Academic Credentials */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
              Academic Background
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>University / College</label>
                <input
                  type="text"
                  value={profile.university || ""}
                  onChange={(e) => setProfile({ ...profile, university: e.target.value })}
                  className="form-input"
                  placeholder="Stanford University"
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Graduation Year</label>
                <input
                  type="number"
                  value={profile.graduation_year || ""}
                  onChange={(e) => setProfile({ ...profile, graduation_year: e.target.value ? Number(e.target.value) : undefined })}
                  className="form-input"
                  placeholder="2026"
                />
              </div>
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Degree Program</label>
              <input
                type="text"
                value={profile.degree || ""}
                onChange={(e) => setProfile({ ...profile, degree: e.target.value })}
                className="form-input"
                placeholder="B.S. in Computer Science"
              />
            </div>
          </div>

          {/* Technical Alignment & Skills */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
              Technical Alignment
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Target Role Title</label>
                <input
                  type="text"
                  value={profile.target_role || ""}
                  onChange={(e) => setProfile({ ...profile, target_role: e.target.value })}
                  className="form-input"
                  placeholder="Software Engineer (Backend)"
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Years of Experience</label>
                {/* Half-years are meaningful, negative years are not. `min`
                    blocks the spinner from stepping below zero; the submit
                    handler rejects a typed or pasted negative rather than
                    quietly rounding it up. */}
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={profile.experience_years ?? ""}
                  onChange={(e) => setProfile({ ...profile, experience_years: e.target.value ? Number(e.target.value) : undefined })}
                  className="form-input"
                  placeholder="0"
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.3rem" }}>Core Skills (comma separated)</label>
              <input
                type="text"
                value={skillsStr}
                onChange={(e) => setSkillsStr(e.target.value)}
                className="form-input"
                placeholder="Python, FastAPI, React, PostgreSQL, Docker"
              />
            </div>
          </div>

          {/* Bio */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "1rem" }}>
              Professional Summary
            </h3>
            <textarea
              rows={3}
              value={profile.bio || ""}
              onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
              className="form-input"
              placeholder="Brief professional background or target career goals..."
            />
          </div>

          {/* Extracted Projects */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.75rem" }}>
              Projects
            </h3>
            {profile.projects && profile.projects.length > 0 ? (
              <ul style={{ listStyleType: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                {profile.projects.map((proj: any, idx: number) => {
                  const title = typeof proj === "string" ? proj : (proj.title || proj.name || proj.heading || proj.project_name || `Project ${idx + 1}`);
                  return (
                    <li key={idx} style={{ fontSize: "0.85rem", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>•</span>
                      <strong>{title}</strong>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "0.825rem", margin: 0 }}>
                No projects extracted from resume yet.
              </p>
            )}
          </div>

          {/* Extracted Experience */}
          <div className="saas-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.75rem" }}>
              Experience
            </h3>
            {profile.experience && profile.experience.length > 0 ? (
              <ul style={{ listStyleType: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                {profile.experience.map((exp: any, idx: number) => {
                  const headline = typeof exp === "string"
                    ? exp
                    : `${exp.role || exp.title || "Role"}${exp.company ? ` at ${exp.company}` : ""}${exp.duration ? ` (${exp.duration})` : ""}`;
                  return (
                    <li key={idx} style={{ fontSize: "0.85rem", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>•</span>
                      <strong>{headline}</strong>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "0.825rem", margin: 0 }}>
                No experience extracted from resume yet.
              </p>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="submit" disabled={saving} className="btn btn-primary" style={{ padding: "0.55rem 1.25rem", fontSize: "0.85rem" }}>
              <Save size={14} /> <span>{saving ? "Saving Changes..." : "Save Settings"}</span>
            </button>
          </div>
        </form>
      </div>
    </WorkspaceLayout>
  );
}
