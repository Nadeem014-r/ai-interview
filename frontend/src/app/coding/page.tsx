"use client";

import React from "react";
import { Navbar } from "@/components/Navbar";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";

export default function CodingInterviewPage() {
  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />
      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "2.5rem 1.5rem" }}>
        <div style={{ marginBottom: "2rem" }}>
          <h2>Coding Sandbox & Algorithm Evaluation</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            Write and execute algorithmic solutions in an isolated execution environment with test case verification.
          </p>
        </div>

        <MonacoCodingRoom onCodeSubmit={(code) => console.log("Submitted code:", code)} />
      </div>
    </div>
  );
}
