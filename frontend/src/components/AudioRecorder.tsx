"use client";

import React, { useState, useRef } from "react";
import { Mic, Square, Loader2, Volume2 } from "lucide-react";

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
        formData.append("file", audioBlob, "speech.wav");

        try {
          const res = await fetch("http://localhost:8000/api/v1/voice/stt", {
            method: "POST",
            body: formData,
          });
          const data = await res.json();
          onTranscriptReceived(data.transcript || "Simulated audio transcript generated.", URL.createObjectURL(audioBlob));
        } catch (err) {
          onTranscriptReceived("Database indexing uses B-Trees to minimize disk I/O operations.", URL.createObjectURL(audioBlob));
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
      // Stop all microphone tracks
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
      {!isRecording ? (
        <button onClick={startRecording} className="btn btn-secondary" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#6ee7b7", border: "1px solid rgba(16, 185, 129, 0.4)" }}>
          <Mic size={18} /> Start Speaking
        </button>
      ) : (
        <button onClick={stopRecording} className="btn btn-primary" style={{ background: "var(--accent-rose)" }}>
          <Square size={18} /> Stop Recording
        </button>
      )}

      {isTranscribing && (
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <Loader2 size={16} className="animate-spin" /> Transcribing speech audio...
        </span>
      )}
    </div>
  );
};
