"use client";

import React, { useEffect, useState, useRef } from "react";
import { Clock } from "lucide-react";

interface InterviewTimerProps {
  initialRemainingSeconds: number;
  isActive: boolean;
  onExpire?: () => void;
}

export const InterviewTimer: React.FC<InterviewTimerProps> = ({
  initialRemainingSeconds,
  isActive,
  onExpire,
}) => {
  const [seconds, setSeconds] = useState<number>(() =>
    initialRemainingSeconds > 0 ? initialRemainingSeconds : 900
  );
  const expiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  const isInitializedRef = useRef(false);

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  // Synchronize initial seconds once when a positive value arrives
  useEffect(() => {
    if (!isInitializedRef.current && initialRemainingSeconds > 0) {
      isInitializedRef.current = true;
      setSeconds(initialRemainingSeconds);
    }
  }, [initialRemainingSeconds]);

  useEffect(() => {
    if (!isActive) return;

    const interval = setInterval(() => {
      setSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (!expiredRef.current) {
            expiredRef.current = true;
            if (onExpireRef.current) {
              onExpireRef.current();
            }
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive]);

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const formattedTime = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  const isLow = seconds < 180;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "0.35rem 0.85rem",
        backgroundColor: isLow ? "var(--accent-rose-light)" : "#f4f4f5",
        border: `1px solid ${isLow ? "#fecdd3" : "#e4e4e7"}`,
        borderRadius: "9999px",
        color: isLow ? "var(--accent-rose)" : "#09090b",
        fontWeight: 700,
        fontFamily: "monospace",
        fontSize: "0.925rem",
        boxShadow: "0 1px 2px rgba(0,0,0,0.04)"
      }}
    >
      <Clock size={15} />
      <span>Time Remaining: {formattedTime}</span>
    </div>
  );
};
