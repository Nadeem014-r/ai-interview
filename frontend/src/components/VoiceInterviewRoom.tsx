"use client";

import React, { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Volume2, Sparkles, Loader2, CheckCircle2, AlertCircle, RefreshCw, Square, Play, RotateCcw, Zap } from "lucide-react";
import { getStoredToken } from "@/lib/auth";

interface VoiceInterviewRoomProps {
  interviewId: number;
  currentQuestionText: string;
  questionNumber: number;
  difficulty: string;
  questionType: string;
  expectedConcepts?: string[];
  lastEvaluation?: {
    overall_question_score: number;
    feedback_text: string;
  } | null;
  onAnswerSubmitted: (transcript: string, audioUrl?: string) => Promise<void>;
  submitting: boolean;
}

type RealtimeVoiceState =
  | "idle"
  | "ai_speaking"
  | "listening"
  | "candidate_speaking"
  | "interrupted"
  | "processing"
  | "ai_responding"
  | "audio_blocked"
  | "error";

// Configurable VAD / Turn-taking Defaults
const VAD_SPEECH_THRESHOLD = 15; // Percent audio level to consider active speech
const VAD_SILENCE_TIMEOUT_MS = 2800; // 2.8s of sustained silence before auto-submission
const VAD_MIN_SPEECH_DURATION_MS = 1200; // 1.2s minimum spoken speech before silence completion activates
const VAD_MAX_RESPONSE_DURATION_MS = 120000; // 2 minutes max response duration
const BARGE_IN_TRIGGER_MS = 400; // 400ms sustained speech to trigger barge-in during AI speaking

export const VoiceInterviewRoom: React.FC<VoiceInterviewRoomProps> = ({
  interviewId,
  currentQuestionText,
  questionNumber,
  difficulty,
  questionType,
  expectedConcepts = [],
  lastEvaluation,
  onAnswerSubmitted,
  submitting,
}) => {
  const [voiceState, setVoiceState] = useState<RealtimeVoiceState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [spokenTranscript, setSpokenTranscript] = useState<string>("");
  const [audioBlobUrl, setAudioBlobUrl] = useState<string | null>(null);
  const [latencyMetrics, setLatencyMetrics] = useState<{ ttsMs?: number; sttMs?: number; totalMs?: number }>({});

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const currentAudioElemRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const lastSpokenQuestionRef = useRef<string>("");

  // VAD & Barge-in Tracking Refs
  const speechStartTimeRef = useRef<number>(0);
  const totalSpeechDurationMsRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const bargeInSpeechDurationRef = useRef<number>(0);
  const turnStartTimeRef = useRef<number>(0);

  // Auto-speak question on new question text
  useEffect(() => {
    if (currentQuestionText && currentQuestionText !== lastSpokenQuestionRef.current) {
      lastSpokenQuestionRef.current = currentQuestionText;
      setSpokenTranscript("");
      setVoiceState("ai_responding");
      speakQuestion(currentQuestionText);
    }
    return () => {
      stopAllAudio();
      stopMicrophone();
    };
  }, [currentQuestionText]);

  const stopAllAudio = () => {
    if (currentAudioElemRef.current) {
      try {
        currentAudioElemRef.current.pause();
      } catch (e) {}
      currentAudioElemRef.current = null;
    }
    if (audioBlobUrl) {
      try {
        URL.revokeObjectURL(audioBlobUrl);
      } catch (e) {}
      setAudioBlobUrl(null);
    }
  };

  const stopMicrophone = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      try {
        audioContextRef.current.close();
      } catch (e) {}
      audioContextRef.current = null;
    }
    setAudioLevel(0);
  };

  // Synthesize and play AI speech with barge-in listener
  const speakQuestion = async (text: string) => {
    try {
      stopAllAudio();
      setVoiceState("ai_speaking");
      setErrorMessage(null);
      const t0 = performance.now();

      const token = getStoredToken();
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      const res = await fetch(`${baseUrl}/voice/tts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        throw new Error(`TTS synthesis failed with status ${res.status}`);
      }

      const ttsDuration = Math.round(performance.now() - t0);
      setLatencyMetrics((m) => ({ ...m, ttsMs: ttsDuration }));

      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      setAudioBlobUrl(audioUrl);

      const audio = new Audio(audioUrl);
      currentAudioElemRef.current = audio;

      // Start background microphone stream for barge-in detection while AI speaks
      startBargeInListener();

      audio.onended = () => {
        // AI finished speaking naturally -> transition to listening
        transitionToListening();
      };

      audio.onerror = (e) => {
        console.warn("Audio playback error:", e);
        transitionToListening();
      };

      try {
        await audio.play();
      } catch (playErr: unknown) {
        const error = playErr as Error;
        if (error && error.name === "NotAllowedError") {
          // Autoplay blocked by browser policy — require explicit candidate gesture
          setVoiceState("audio_blocked");
          return;
        }
        console.warn("Audio play exception:", playErr);
        transitionToListening();
      }
    } catch (err) {
      console.warn("TTS synthesis fallback:", err);
      transitionToListening();
    }
  };

  // Start background microphone to monitor for candidate speech during AI speaking (Barge-In)
  const startBargeInListener = async () => {
    try {
      if (streamRef.current) return; // Stream already active
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      setHasPermission(true);

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyserRef.current = analyser;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      bargeInSpeechDurationRef.current = 0;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const checkBargeIn = () => {
        if (!analyserRef.current || !currentAudioElemRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const level = Math.min(100, Math.round((avg / 128) * 100));
        setAudioLevel(level);

        if (level >= VAD_SPEECH_THRESHOLD) {
          bargeInSpeechDurationRef.current += 50;
          if (bargeInSpeechDurationRef.current >= BARGE_IN_TRIGGER_MS) {
            // Sustained meaningful candidate speech detected during AI speaking -> Trigger Barge-In
            console.log("Candidate Barge-In detected. Pausing AI audio.");
            stopAllAudio();
            setVoiceState("interrupted");
            setTimeout(() => transitionToListening(true), 150);
            return;
          }
        } else {
          bargeInSpeechDurationRef.current = Math.max(0, bargeInSpeechDurationRef.current - 25);
        }

        animationFrameRef.current = requestAnimationFrame(checkBargeIn);
      };

      checkBargeIn();
    } catch (e) {
      console.warn("Barge-in microphone listener unavailable:", e);
    }
  };

  // Transition to active listening mode with full VAD silence detection
  const transitionToListening = async (fromBargeIn: boolean = false) => {
    try {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      setVoiceState(fromBargeIn ? "interrupted" : "listening");
      setErrorMessage(null);
      turnStartTimeRef.current = performance.now();
      speechStartTimeRef.current = 0;
      totalSpeechDurationMsRef.current = 0;
      lastSpeechTimeRef.current = performance.now();

      let stream = streamRef.current;
      if (!stream || stream.getAudioTracks().every((t) => t.readyState === "ended")) {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;
      }
      setHasPermission(true);

      if (!audioContextRef.current || audioContextRef.current.state === "closed") {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const audioCtx = new AudioCtx();
        audioContextRef.current = audioCtx;
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 128;
        analyserRef.current = analyser;
        const source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);
      }

      const analyser = analyserRef.current!;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // Setup MediaRecorder
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
        await handleAudioCaptured(audioBlob);
      };

      mediaRecorder.start(200);

      // VAD & Silence Loop
      const vadLoop = () => {
        if (!analyserRef.current || mediaRecorder.state !== "recording") return;

        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const level = Math.min(100, Math.round((avg / 128) * 100));
        setAudioLevel(level);

        const now = performance.now();

        if (level >= VAD_SPEECH_THRESHOLD) {
          // Candidate active speech
          if (!speechStartTimeRef.current) speechStartTimeRef.current = now;
          totalSpeechDurationMsRef.current += 50;
          lastSpeechTimeRef.current = now;
          setVoiceState("candidate_speaking");
        } else {
          // Silence or natural pause
          const silenceDuration = now - lastSpeechTimeRef.current;
          const totalSpoken = totalSpeechDurationMsRef.current;

          // Auto-finish if candidate spoke substantially and then paused naturally for > 2.8s
          if (totalSpoken >= VAD_MIN_SPEECH_DURATION_MS && silenceDuration >= VAD_SILENCE_TIMEOUT_MS) {
            console.log("VAD detected completion of answer (natural silence).");
            finishSpeaking();
            return;
          }

          // Max response duration guard
          if (now - turnStartTimeRef.current >= VAD_MAX_RESPONSE_DURATION_MS) {
            console.log("Max response duration reached.");
            finishSpeaking();
            return;
          }
        }

        animationFrameRef.current = requestAnimationFrame(vadLoop);
      };

      vadLoop();
    } catch (err) {
      console.error("Microphone activation error:", err);
      setHasPermission(false);
      setVoiceState("error");
      setErrorMessage("Microphone access denied or unavailable. Please grant microphone permissions.");
    }
  };

  // Candidate finishes speaking
  const finishSpeaking = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      setVoiceState("processing");
      mediaRecorderRef.current.stop();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    }
  };

  // Process captured audio through STT and submit to interview brain
  const handleAudioCaptured = async (audioBlob: Blob) => {
    try {
      setVoiceState("processing");
      const t0 = performance.now();
      const token = getStoredToken();
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      const formData = new FormData();
      formData.append("file", audioBlob, "answer_turn.wav");

      const sttRes = await fetch(`${baseUrl}/voice/stt`, {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
      });

      if (!sttRes.ok) {
        throw new Error("STT speech transcription failed.");
      }

      const sttDuration = Math.round(performance.now() - t0);
      setLatencyMetrics((m) => ({ ...m, sttMs: sttDuration }));

      const sttData = await sttRes.json();
      const transcript = (sttData.transcript || sttData.text || "").trim();

      if (!transcript || transcript.length < 3) {
        setVoiceState("error");
        setErrorMessage("I didn't catch that clearly. Please speak naturally into your microphone and try again.");
        return;
      }

      setSpokenTranscript(transcript);
      const audioUrl = URL.createObjectURL(audioBlob);

      const totalTurnMs = Math.round(performance.now() - turnStartTimeRef.current);
      setLatencyMetrics((m) => ({ ...m, totalMs: totalTurnMs }));

      // Submit transcript to existing interview engine
      await onAnswerSubmitted(transcript, audioUrl);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to process speech";
      setVoiceState("error");
      setErrorMessage(errorMsg || "An error occurred while processing speech. Click below to retry speaking.");
    }
  };

  // Unblock autoplay and start audio playback on user click
  const handleUnblockAudio = async () => {
    if (currentAudioElemRef.current) {
      try {
        setVoiceState("ai_speaking");
        await currentAudioElemRef.current.play();
      } catch (err) {
        transitionToListening();
      }
    } else {
      speakQuestion(currentQuestionText);
    }
  };

  // Replay question audio without altering interview state
  const handleReplayQuestion = () => {
    if (submitting || voiceState === "processing") return;
    speakQuestion(currentQuestionText);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", marginBottom: "1.5rem" }}>
      {/* Visual AI Interviewer Stage */}
      <div
        className="saas-card"
        style={{
          background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
          color: "#ffffff",
          borderRadius: "20px",
          padding: "2.5rem 2rem",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          position: "relative",
          overflow: "hidden",
          boxShadow: "0 10px 25px -5px rgba(15, 23, 42, 0.3)",
        }}
      >
        {/* State Badge */}
        <div style={{ marginBottom: "1.5rem" }}>
          {voiceState === "ai_speaking" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(99, 102, 241, 0.25)",
                border: "1px solid rgba(129, 140, 248, 0.5)",
                color: "#a5b4fc",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Volume2 size={16} className="animate-pulse" /> Interviewer is speaking...
            </span>
          )}

          {voiceState === "interrupted" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(236, 72, 153, 0.25)",
                border: "1px solid rgba(244, 114, 182, 0.5)",
                color: "#f472b6",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Zap size={16} /> Interrupted — Listening to you
            </span>
          )}

          {voiceState === "listening" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(16, 185, 129, 0.25)",
                border: "1px solid rgba(52, 211, 153, 0.5)",
                color: "#6ee7b7",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Mic size={16} className="animate-bounce" /> Listening... Speak naturally
            </span>
          )}

          {voiceState === "candidate_speaking" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(16, 185, 129, 0.35)",
                border: "1px solid #10b981",
                color: "#34d399",
                fontSize: "0.85rem",
                fontWeight: 700,
              }}
            >
              <Mic size={16} /> Candidate Speaking...
            </span>
          )}

          {voiceState === "processing" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(245, 158, 11, 0.25)",
                border: "1px solid rgba(251, 191, 36, 0.5)",
                color: "#fcd34d",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Loader2 size={16} className="animate-spin" /> Processing your answer...
            </span>
          )}

          {voiceState === "ai_responding" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(99, 102, 241, 0.25)",
                border: "1px solid rgba(129, 140, 248, 0.5)",
                color: "#a5b4fc",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Sparkles size={16} /> Preparing Next Question...
            </span>
          )}

          {voiceState === "audio_blocked" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(245, 158, 11, 0.25)",
                border: "1px solid rgba(251, 191, 36, 0.5)",
                color: "#fcd34d",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <Volume2 size={16} /> Audio Ready — Click to Start Listening
            </span>
          )}

          {voiceState === "error" && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.4rem 1.1rem",
                borderRadius: "9999px",
                background: "rgba(239, 68, 68, 0.25)",
                border: "1px solid rgba(248, 113, 113, 0.5)",
                color: "#fca5a5",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              <AlertCircle size={16} /> Needs Attention
            </span>
          )}
        </div>

        {/* Dynamic AI Pulse Orb Visualizer */}
        <div
          style={{
            position: "relative",
            width: "120px",
            height: "120px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "1.75rem",
          }}
        >
          {/* Animated Wave Rings */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              background:
                voiceState === "ai_speaking"
                  ? "radial-gradient(circle, rgba(99,102,241,0.6) 0%, rgba(99,102,241,0) 70%)"
                  : voiceState === "candidate_speaking" || voiceState === "listening"
                  ? "radial-gradient(circle, rgba(16,185,129,0.6) 0%, rgba(16,185,129,0) 70%)"
                  : voiceState === "interrupted"
                  ? "radial-gradient(circle, rgba(236,72,153,0.6) 0%, rgba(236,72,153,0) 70%)"
                  : "radial-gradient(circle, rgba(148,163,184,0.3) 0%, rgba(148,163,184,0) 70%)",
              transform: `scale(${1 + (audioLevel / 100) * 0.45})`,
              transition: "transform 0.08s ease-out",
            }}
          />

          {/* Central AI Orb */}
          <div
            style={{
              width: "80px",
              height: "80px",
              borderRadius: "50%",
              background:
                voiceState === "ai_speaking"
                  ? "linear-gradient(135deg, #6366f1 0%, #4338ca 100%)"
                  : voiceState === "candidate_speaking" || voiceState === "listening"
                  ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                  : voiceState === "interrupted"
                  ? "linear-gradient(135deg, #ec4899 0%, #be185d 100%)"
                  : "linear-gradient(135deg, #475569 0%, #1e293b 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 30px rgba(99, 102, 241, 0.5)",
              zIndex: 2,
            }}
          >
            {voiceState === "ai_speaking" && <Volume2 size={36} color="#ffffff" />}
            {voiceState === "audio_blocked" && <Play size={36} color="#ffffff" />}
            {(voiceState === "listening" || voiceState === "candidate_speaking" || voiceState === "interrupted") && (
              <Mic size={36} color="#ffffff" />
            )}
            {voiceState === "processing" && <Loader2 size={36} color="#ffffff" className="animate-spin" />}
            {voiceState === "error" && <MicOff size={36} color="#fca5a5" />}
            {(voiceState === "idle" || voiceState === "ai_responding") && <Sparkles size={36} color="#cbd5e1" />}
          </div>
        </div>

        {/* Spoken Question Title Displayed Clearly */}
        <div style={{ maxWidth: "800px", margin: "0 auto" }}>
          <div style={{ fontSize: "0.85rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
            Question #{questionNumber} • {questionType} ({difficulty})
          </div>
          <h2 style={{ fontSize: "1.45rem", fontWeight: 700, color: "#f8fafc", lineHeight: 1.4, margin: "0 0 1rem 0" }}>
            &ldquo;{currentQuestionText}&rdquo;
          </h2>

          {expectedConcepts.length > 0 && (
            <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", gap: "0.4rem" }}>
              {expectedConcepts.map((c) => (
                <span
                  key={c}
                  style={{
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(255, 255, 255, 0.2)",
                    borderRadius: "6px",
                    padding: "0.2rem 0.6rem",
                    fontSize: "0.75rem",
                    color: "#cbd5e1",
                  }}
                >
                  Focus: {c}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Live Audio Level Equalizer Bar (Active when listening/speaking) */}
        {(voiceState === "listening" || voiceState === "candidate_speaking" || voiceState === "interrupted") && (
          <div style={{ width: "100%", maxWidth: "320px", marginTop: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#6ee7b7", marginBottom: "0.3rem" }}>
              <span>Microphone Live</span>
              <span>{audioLevel}% (Auto-pause detect active)</span>
            </div>
            <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${Math.max(5, audioLevel)}%`,
                  background: voiceState === "candidate_speaking" ? "#10b981" : "#34d399",
                  transition: "width 0.08s ease-out",
                }}
              />
            </div>
          </div>
        )}

        {/* Action Controls */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", justifyContent: "center", gap: "1rem", marginTop: "2rem" }}>
          {voiceState === "audio_blocked" && (
            <button
              onClick={handleUnblockAudio}
              className="btn btn-primary"
              style={{
                background: "#6366f1",
                padding: "0.75rem 1.75rem",
                fontSize: "0.95rem",
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
              }}
            >
              <Play size={18} /> Enable & Play Spoken Question
            </button>
          )}

          {(voiceState === "listening" || voiceState === "candidate_speaking" || voiceState === "interrupted") && (
            <>
              <button
                onClick={finishSpeaking}
                disabled={submitting}
                className="btn btn-primary"
                style={{
                  background: "#10b981",
                  borderColor: "#059669",
                  padding: "0.75rem 1.75rem",
                  fontSize: "0.95rem",
                  borderRadius: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
                }}
              >
                <Square size={18} /> Finish Speaking
              </button>

              <button
                onClick={handleReplayQuestion}
                className="btn btn-secondary"
                style={{
                  background: "rgba(255, 255, 255, 0.15)",
                  border: "1px solid rgba(255, 255, 255, 0.25)",
                  color: "#ffffff",
                  padding: "0.75rem 1.25rem",
                  fontSize: "0.85rem",
                  borderRadius: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                <RotateCcw size={16} /> Replay Question (🔊)
              </button>
            </>
          )}

          {voiceState === "ai_speaking" && (
            <button
              onClick={() => {
                stopAllAudio();
                transitionToListening(true);
              }}
              style={{
                background: "rgba(255, 255, 255, 0.15)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                color: "#ffffff",
                padding: "0.5rem 1.25rem",
                borderRadius: "10px",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              Skip Speaking & Answer Now
            </button>
          )}

          {(voiceState === "error" || voiceState === "idle") && (
            <>
              <button
                onClick={() => transitionToListening()}
                disabled={submitting}
                className="btn btn-primary"
                style={{
                  background: "#6366f1",
                  padding: "0.75rem 1.75rem",
                  fontSize: "0.95rem",
                  borderRadius: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <RefreshCw size={18} /> Retry Speaking
              </button>

              <button
                onClick={handleReplayQuestion}
                className="btn btn-secondary"
                style={{
                  background: "rgba(255, 255, 255, 0.15)",
                  border: "1px solid rgba(255, 255, 255, 0.25)",
                  color: "#ffffff",
                  padding: "0.75rem 1.25rem",
                  fontSize: "0.85rem",
                  borderRadius: "12px",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                <RotateCcw size={16} /> Replay Question (🔊)
              </button>
            </>
          )}
        </div>

        {/* Error / Instructions Notice */}
        {errorMessage && (
          <div
            style={{
              marginTop: "1.25rem",
              background: "rgba(239, 68, 68, 0.2)",
              border: "1px solid rgba(248, 113, 113, 0.4)",
              borderRadius: "10px",
              padding: "0.75rem 1.25rem",
              color: "#fca5a5",
              fontSize: "0.85rem",
              maxWidth: "600px",
            }}
          >
            {errorMessage}
          </div>
        )}
      </div>

      {/* Recognized Speech Transcript Display */}
      {spokenTranscript && (
        <div
          className="saas-card"
          style={{
            padding: "1.25rem 1.5rem",
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "14px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
            <span style={{ fontSize: "0.8rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
              You Spoke (Transcribed):
            </span>
            {latencyMetrics.sttMs && (
              <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                STT Latency: {latencyMetrics.sttMs}ms
              </span>
            )}
          </div>
          <p style={{ color: "#0f172a", fontSize: "0.95rem", lineHeight: 1.5, margin: 0, fontStyle: "italic" }}>
            &ldquo;{spokenTranscript}&rdquo;
          </p>
        </div>
      )}

      {/* Realtime Last Turn Evaluation Feedback */}
      {lastEvaluation && (
        <div
          className="saas-card"
          style={{
            padding: "1.25rem 1.5rem",
            backgroundColor: "#ecfdf5",
            border: "1px solid #a7f3d0",
            borderRadius: "14px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#047857", marginBottom: "0.35rem" }}>
            <CheckCircle2 size={18} />
            <strong style={{ fontSize: "0.95rem" }}>Previous Turn Evaluation: {lastEvaluation.overall_question_score} / 10</strong>
          </div>
          <p style={{ color: "#334155", fontSize: "0.88rem", lineHeight: 1.5, margin: 0 }}>
            {lastEvaluation.feedback_text}
          </p>
        </div>
      )}
    </div>
  );
};
