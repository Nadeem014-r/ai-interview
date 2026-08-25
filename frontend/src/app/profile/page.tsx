"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { apiRequest } from "@/lib/api";
import { CandidateProfile } from "@/types";
import { User, Save, CheckCircle2, GraduationCap, Code2, Briefcase, Phone, Mail } from "lucide-react";

export default function ProfilePage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [headline, setHeadline] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [level, setLevel] = useState("entry");
  const [university, setUniversity] = useState("");
  const [degree, setDegree] = useState("");
  const [branch, setBranch] = useState("");
  const [gradYear, setGradYear] = useState<number | "">("");
  const [skillsStr, setSkillsStr] = useState("");
  const [bio, setBio] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadProfile() {
      try {
        const prof: CandidateProfile = await apiRequest("/profile");
        if (prof) {
          setFullName(prof.full_name || "");
          setEmail(prof.email || "");
          setPhone(prof.phone || "");
          setHeadline(prof.headline || "");
          setTargetRole(prof.target_role || "");
          setLevel(prof.experience_level || "entry");
          setUniversity(prof.university || "");
          setDegree(prof.degree || "");
          setBranch(prof.branch || "");
          setGradYear(prof.graduation_year || "");
          setSkillsStr(prof.skills ? prof.skills.join(", ") : "");
          setBio(prof.bio || "");
          setGithubUrl(prof.github_url || "");
          setLinkedinUrl(prof.linkedin_url || "");
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(false);
    try {
      const skillsArray = skillsStr
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      await apiRequest("/profile", {
        method: "PUT",
        body: JSON.stringify({
          full_name: fullName,
          phone,
          headline,
          target_role: targetRole,
          experience_level: level,
          university,
          degree,
          branch,
          graduation_year: gradYear ? Number(gradYear) : null,
          skills: skillsArray,
          bio,
          github_url: githubUrl,
          linkedin_url: linkedinUrl
        })
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (err: any) {
      alert(err.message || "Failed to update profile.");
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh" }}>
        <Navbar />
        <div style={{ textAlign: "center", padding: "4rem", color: "var(--text-secondary)" }}>
          Loading candidate profile...
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />
      <div style={{ maxWidth: "850px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div className="glass-card" style={{ padding: "2.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <User size={28} color="var(--primary)" />
            <div>
              <h2 style={{ margin: 0 }}>Candidate Profile & Placement Settings</h2>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Data is persisted in the authoritative PostgreSQL/SQLite database</span>
            </div>
          </div>

          {saved && (
            <div style={{ padding: "0.75rem 1rem", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "var(--radius-md)", color: "#6ee7b7", fontSize: "0.85rem", marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <CheckCircle2 size={16} /> Candidate profile updated and persisted successfully!
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Personal Details */}
            <div style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1.25rem" }}>
              <h4 style={{ fontSize: "1rem", color: "var(--accent-cyan)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <User size={18} /> Personal & Contact Info
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Full Name</label>
                  <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} className="form-input" placeholder="Alex Mercer" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Email Address</label>
                  <input type="email" disabled value={email} className="form-input" style={{ opacity: 0.7, cursor: "not-allowed" }} />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Phone Number</label>
                  <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} className="form-input" placeholder="+1 (555) 019-2834" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Professional Headline</label>
                  <input type="text" value={headline} onChange={(e) => setHeadline(e.target.value)} className="form-input" placeholder="Aspiring Full-Stack & Systems Engineer" />
                </div>
              </div>
            </div>

            {/* Academic & University Details */}
            <div style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1.25rem" }}>
              <h4 style={{ fontSize: "1rem", color: "var(--primary)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <GraduationCap size={18} /> Education & Academic Background
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>University / College</label>
                  <input type="text" value={university} onChange={(e) => setUniversity(e.target.value)} className="form-input" placeholder="National Institute of Technology" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Degree</label>
                  <input type="text" value={degree} onChange={(e) => setDegree(e.target.value)} className="form-input" placeholder="B.Tech" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Branch / Major</label>
                  <input type="text" value={branch} onChange={(e) => setBranch(e.target.value)} className="form-input" placeholder="Computer Science & Engineering" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Graduation Year</label>
                  <input type="number" value={gradYear} onChange={(e) => setGradYear(e.target.value ? Number(e.target.value) : "")} className="form-input" placeholder="2025" />
                </div>
              </div>
            </div>

            {/* Career & Skills */}
            <div style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1.25rem" }}>
              <h4 style={{ fontSize: "1rem", color: "var(--accent-emerald)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Code2 size={18} /> Technical Skills & Target Role
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Primary Target Role</label>
                  <input type="text" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="form-input" placeholder="Software Engineer (Backend)" />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Target Seniority / Level</label>
                  <select value={level} onChange={(e) => setLevel(e.target.value)} className="form-input">
                    <option value="entry">Entry Level / Graduate (L3)</option>
                    <option value="mid">Mid Level Engineer (L4)</option>
                    <option value="senior">Senior Engineer (L5)</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>
                  Skills & Technologies (comma-separated)
                </label>
                <input
                  type="text"
                  value={skillsStr}
                  onChange={(e) => setSkillsStr(e.target.value)}
                  className="form-input"
                  placeholder="Python, FastAPI, PostgreSQL, Docker, Data Structures, Redis"
                />
              </div>
            </div>

            {/* Bio */}
            <div>
              <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.4rem" }}>Bio & Technical Summary</label>
              <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3} className="form-input" placeholder="Brief summary of your background, areas of focus, and aspirations..." />
            </div>

            <button type="submit" className="btn btn-primary" style={{ padding: "0.85rem", fontSize: "1rem", marginTop: "0.5rem" }}>
              <Save size={18} /> Save & Persist Profile Changes
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

