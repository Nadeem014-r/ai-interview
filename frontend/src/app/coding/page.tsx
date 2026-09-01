"use client";

import React from "react";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";
import { Code2 } from "lucide-react";

export default function CodingInterviewPage() {
  return (
    <WorkspaceLayout sectionTitle="Coding Sandbox" sectionSubtitle="Algorithmic problem execution & code evaluation">
      <div style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", letterSpacing: "-0.02em", margin: 0 }}>
          Algorithm & Code Execution Sandbox
        </h2>
        <p style={{ color: "#71717a", fontSize: "0.85rem", marginTop: "0.2rem" }}>
          Write, test, and execute algorithmic solutions in an isolated browser-based Monaco editor environment.
        </p>
      </div>

      <MonacoCodingRoom onCodeSubmit={(code) => console.log("Submitted code:", code)} />
    </WorkspaceLayout>
  );
}
