"use client";

import React, { useEffect, useState } from "react";
import { Clock } from "lucide-react";

interface InterviewTimerProps {
  initialRemainingSeconds: number;
  onExpire?: () => void;
}

export const InterviewTimer: React.FC<InterviewTimerProps> = ({ initialRemainingSeconds, onExpire }) => {
  const [seconds, setSeconds] = useState(initialRemainingSeconds);

  useEffect(() => {
    setSeconds(initialRemainingSeconds);
  }, [initialRemainingSeconds]);

  useEffect(() => {
    if (seconds <= 0) {
      if (onExpire) onExpire();
      return;
    }
    const interval = setInterval(() => {
      setSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (onExpire) onExpire();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [seconds, onExpire]);

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const formattedTime = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

  const isLow = seconds < 180;

  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "0.5rem",
      padding: "0.4rem 0.9rem",
      background: isLow ? "rgba(244, 63, 94, 0.15)" : "rgba(99, 102, 241, 0.15)",
      border: `1px solid ${isLow ? "rgba(244, 63, 94, 0.4)" : "rgba(99, 102, 241, 0.4)"}`,
      borderRadius: "var(--radius-full)",
      color: isLow ? "#fda4af" : "#a5b4fc",
      fontWeight: 700,
      fontFamily: "monospace",
      fontSize: "1rem"
    }}>
      <Clock size={18} />
      <span>{formattedTime}</span>
    </div>
  );
};
