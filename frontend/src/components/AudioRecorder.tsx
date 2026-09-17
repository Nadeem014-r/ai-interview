"use client";

import React, { useState, useRef } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { getStoredToken } from "@/lib/auth";

interface AudioRecorderProps {
  onTranscriptReceived: (transcript: string, audioUrl?: string) => void;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({ onTranscriptReceived }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        setIsTranscribing(true);
        
        // Send audio file to STT backend endpoint
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.wav");
        const token = getStoredToken();
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

        try {
          const res = await fetch(`${baseUrl}/voice/stt`, {
            method: "POST",
            headers: {
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: formData,
          });
          if (res.ok) {
            const data = await res.json();
            const transcript = (data.transcript || data.text || "").trim();
            if (transcript) {
              onTranscriptReceived(transcript, URL.createObjectURL(audioBlob));
            } else {
              alert("No clear candidate speech was detected in the recording. Please speak clearly into your microphone.");
            }
          } else {
            alert("Speech-to-text processing failed. Please try speaking again.");
          }
        } catch (err) {
          console.error("STT transcription network error:", err);
          alert("Unable to connect to speech transcription service. Please try again.");
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      alert("Microphone access denied or unsupported browser.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
      {!isRecording ? (
        <button onClick={startRecording} className="btn btn-secondary" style={{ backgroundColor: "var(--accent-emerald-light)", color: "var(--accent-emerald)", borderColor: "rgba(52, 211, 153, 0.32)", fontSize: "0.825rem" }}>
          <Mic size={15} /> <span>Start Speaking</span>
        </button>
      ) : (
        <button onClick={stopRecording} className="btn btn-primary" style={{ backgroundColor: "var(--accent-rose)", borderColor: "var(--accent-rose)", fontSize: "0.825rem" }}>
          <Square size={14} /> <span>Stop Recording</span>
        </button>
      )}

      {isTranscribing && (
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <Loader2 size={14} className="spin" /> Transcribing speech audio...
        </span>
      )}
    </div>
  );
};
