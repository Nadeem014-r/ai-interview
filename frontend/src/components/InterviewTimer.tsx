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
        padding: "0.38rem 0.9rem",
        background: isLow
          ? "linear-gradient(135deg, rgba(251, 113, 133, 0.22) 0%, rgba(251, 113, 133, 0.10) 100%)"
          : "linear-gradient(135deg, rgba(255, 255, 255, 0.10) 0%, rgba(255, 255, 255, 0.04) 100%)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: `1px solid ${isLow ? "rgba(251, 113, 133, 0.45)" : "rgba(255, 255, 255, 0.14)"}`,
        borderRadius: "9999px",
        color: isLow ? "#fda4af" : "var(--text-primary)",
        fontWeight: 700,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontVariantNumeric: "tabular-nums",
        letterSpacing: "0.01em",
        fontSize: "0.925rem",
        boxShadow: isLow
          ? "0 0 22px -6px rgba(251, 113, 133, 0.6), 0 1px 0 rgba(255, 255, 255, 0.12) inset"
          : "0 0 20px -8px rgba(124, 92, 255, 0.55), 0 1px 0 rgba(255, 255, 255, 0.12) inset"
      }}
    >
      <Clock size={15} />
      <span>Time Remaining: {formattedTime}</span>
    </div>
  );
};
