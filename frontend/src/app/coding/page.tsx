"use client";

import React, { useState } from "react";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";

const PRACTICE_QUESTION =
  "Practice exercise. Given a string, find the length of the longest substring that " +
  "contains no repeated characters. Explain your approach and its complexity in comments.";

export default function CodingPracticePage() {
  const [submitted, setSubmitted] = useState(false);

  return (
    <WorkspaceLayout
      sectionTitle="Coding Practice"
      sectionSubtitle="Practise in the same workspace used during an interview"
    >
      <div style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
          Coding Workspace
        </h2>
        <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          A standalone copy of the in-interview editor. Nothing written here is compiled, run or
          recorded &mdash; it is for getting used to the workspace before a real session.
        </p>
      </div>

      <MonacoCodingRoom
        questionText={PRACTICE_QUESTION}
        expectedConcepts={["Sliding window", "Two pointers", "O(n) time complexity"]}
        onCodeSubmit={() => setSubmitted(true)}
        submitting={false}
        submitted={submitted}
      />
    </WorkspaceLayout>
  );
}
