"use client";

import React from "react";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";

const PRACTICE_QUESTION =
  "Practice exercise. Given a string, find the length of the longest substring that " +
  "contains no repeated characters. Explain your approach and its complexity in comments.";

export default function CodingPracticePage() {
  return (
    <WorkspaceLayout
      sectionTitle="Coding Practice"
      sectionSubtitle="Practise in the same workspace used during an interview"
    >
      <div style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", margin: 0 }}>
          Practice Workspace
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          A standalone copy of the in-interview editor, for getting used to the workspace before a
          real session. Nothing written here is compiled, run, saved, submitted or assessed. Coding
          questions inside an interview appear in the interview itself, not here.
        </p>
      </div>

      <MonacoCodingRoom
        questionText={PRACTICE_QUESTION}
        expectedConcepts={["Sliding window", "Two pointers", "O(n) time complexity"]}
        practice
      />
    </WorkspaceLayout>
  );
}
