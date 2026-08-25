"use client";

import React, { useEffect, useRef, useState } from "react";
import { Camera, CameraOff, Mic, MicOff, ShieldCheck } from "lucide-react";

interface VideoInteractionRoomProps {
  currentQuestionText: string;
}

export const VideoInteractionRoom: React.FC<VideoInteractionRoomProps> = ({ currentQuestionText }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [micActive, setMicActive] = useState(true);
  const [consentGranted, setConsentGranted] = useState(false);

  useEffect(() => {
    if (consentGranted) {
      enableCamera();
    }
    return () => {
      stopCamera();
    };
  }, [consentGranted]);

  const enableCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraActive(true);
    } catch (err) {
      console.warn("Video stream unavailable or consent rejected.");
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  return (
    <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      {!consentGranted ? (
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <ShieldCheck size={48} color="var(--primary)" style={{ marginBottom: "1rem" }} />
          <h3>Video Interview Mode Consent</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", margin: "1rem 0 1.5rem" }}>
            The platform requires explicit consent to access your camera and microphone for live voice interaction.
            <br />
            <strong>Ethical AI Notice:</strong> Facial appearance and facial emotions are NEVER used as hiring or technical interview scores.
          </p>
          <button onClick={() => setConsentGranted(true)} className="btn btn-primary">
            I Consent & Grant Camera Access
          </button>
        </div>
      ) : (
        <div>
          <div style={{ position: "relative", width: "100%", height: "320px", background: "#000", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            
            <div style={{ position: "absolute", bottom: "1rem", left: "1rem", right: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ background: "rgba(0,0,0,0.6)", padding: "0.4rem 0.8rem", borderRadius: "var(--radius-md)", fontSize: "0.8rem" }}>
                🔴 Live Video Interaction Stream
              </div>

              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button onClick={() => setMicActive(!micActive)} className="btn btn-secondary" style={{ padding: "0.4rem 0.8rem" }}>
                  {micActive ? <Mic size={16} /> : <MicOff size={16} color="var(--accent-rose)" />}
                </button>
                <button onClick={() => { if (cameraActive) stopCamera(); else enableCamera(); }} className="btn btn-secondary" style={{ padding: "0.4rem 0.8rem" }}>
                  {cameraActive ? <Camera size={16} /> : <CameraOff size={16} color="var(--accent-rose)" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
