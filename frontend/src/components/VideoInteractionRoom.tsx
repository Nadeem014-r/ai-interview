"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  Mic,
  MicOff,
  ShieldCheck,
  Volume2,
  Sparkles,
  RefreshCw,
  Square,
  Play,
  RotateCcw,
  Zap,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Video,
  UserCheck,
  ChevronDown
} from "lucide-react";
import { getStoredToken } from "@/lib/auth";

export interface VideoInteractionRoomProps {
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
  companyName?: string;
  roleTitle?: string;
}

type RealtimeVideoState =
  | "idle"
  | "ai_speaking"
  | "listening"
  | "candidate_speaking"
  | "interrupted"
  | "processing"
  | "ai_responding"
  | "audio_blocked"
  | "error";

interface InterviewerPersona {
  id: string;
  name: string;
  title: string;
  avatarUrl: string;
  badge: string;
}

const PERSONAS: InterviewerPersona[] = [
  {
    id: "dr_eleanor",
    name: "Dr. Eleanor Vance",
    title: "Engineering Director & Hiring Lead",
    avatarUrl: "/avatars/vp_engineering.jpg",
    badge: "AI Senior Interviewer"
  },
  {
    id: "david_sterling",
    name: "David Sterling",
    title: "Staff Software Engineer & System Architect",
    avatarUrl: "/avatars/senior_tech_lead.jpg",
    badge: "Technical Panelist"
  },
  {
    id: "alex_morgan",
    name: "Alex Morgan",
    title: "VP of Engineering",
    avatarUrl: "/avatars/executive_recruiter.jpg",
    badge: "Leadership & Culture Lead"
  }
];

// Configurable VAD / Turn-taking Constants
const VAD_SPEECH_THRESHOLD = 14; // Audio level threshold (0-100) to trigger active speech
const VAD_SILENCE_TIMEOUT_MS = 2800; // 2.8s of sustained silence before auto-submission
const VAD_MIN_SPEECH_DURATION_MS = 1200; // 1.2s minimum spoken speech before silence completion activates
const VAD_MAX_RESPONSE_DURATION_MS = 120000; // 2 minutes max response duration
const BARGE_IN_TRIGGER_MS = 400; // 400ms sustained speech to trigger barge-in during AI speaking

export const VideoInteractionRoom: React.FC<VideoInteractionRoomProps> = ({
  interviewId,
  currentQuestionText,
  questionNumber,
  difficulty,
  questionType,
  expectedConcepts = [],
  lastEvaluation,
  onAnswerSubmitted,
  submitting,
  companyName = "Tech Corp",
  roleTitle = "Software Engineer"
}) => {
  // Interaction & Permission states
  const [consentGranted, setConsentGranted] = useState(false);
  const [cameraActive, setCameraActive] = useState(true);
  const [micActive, setMicActive] = useState(true);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  // Avatar persona selection
  const [selectedPersona, setSelectedPersona] = useState<InterviewerPersona>(PERSONAS[0]);
  const [showPersonaSelector, setShowPersonaSelector] = useState(false);

  // Lifecycle State Machine
  const [voiceState, setVoiceState] = useState<RealtimeVideoState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [candidateAudioLevel, setCandidateAudioLevel] = useState<number>(0);
  const [interviewerAudioLevel, setInterviewerAudioLevel] = useState<number>(0);
  const [spokenTranscript, setSpokenTranscript] = useState<string>("");
  const [audioBlobUrl, setAudioBlobUrl] = useState<string | null>(null);
  const [latencyMetrics, setLatencyMetrics] = useState<{ ttsMs?: number; sttMs?: number; totalMs?: number }>({});

  // Media & Web Audio references
  const candidateVideoRef = useRef<HTMLVideoElement | null>(null);
  const candidateStreamRef = useRef<MediaStream | null>(null);
  const currentAudioElemRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Web Audio Analysers
  const candidateAudioCtxRef = useRef<AudioContext | null>(null);
  const candidateAnalyserRef = useRef<AnalyserNode | null>(null);
  const ttsAudioCtxRef = useRef<AudioContext | null>(null);
  const ttsAnalyserRef = useRef<AnalyserNode | null>(null);
  const ttsSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const ttsAnimFrameRef = useRef<number | null>(null);

  // Question & Speech Tracking
  const lastSpokenQuestionRef = useRef<string>("");
  const speechStartTimeRef = useRef<number>(0);
  const totalSpeechDurationMsRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const bargeInSpeechDurationRef = useRef<number>(0);
  const turnStartTimeRef = useRef<number>(0);

  // Frequency visualizer bars for AI Interviewer audio
  const [frequencyBars, setFrequencyBars] = useState<number[]>([10, 15, 20, 15, 10]);

  // Clean cleanup on unmount
  useEffect(() => {
    return () => {
      stopAllAudio();
      stopCandidateMedia();
    };
  }, []);

  // When consent is granted, initialize camera feed
  useEffect(() => {
    if (consentGranted) {
      enableCandidateCamera();
    }
  }, [consentGranted]);

  // When currentQuestionText changes and consent granted -> synthesize & speak
  useEffect(() => {
    if (consentGranted && currentQuestionText && currentQuestionText !== lastSpokenQuestionRef.current) {
      lastSpokenQuestionRef.current = currentQuestionText;
      setSpokenTranscript("");
      setVoiceState("ai_responding");
      speakQuestion(currentQuestionText);
    }
  }, [currentQuestionText, consentGranted]);

  // Cleanup helper for all audio elements & contexts
  const stopAllAudio = () => {
    if (ttsAnimFrameRef.current) {
      cancelAnimationFrame(ttsAnimFrameRef.current);
      ttsAnimFrameRef.current = null;
    }
    if (currentAudioElemRef.current) {
      try {
        currentAudioElemRef.current.onplay = null;
        currentAudioElemRef.current.onplaying = null;
        currentAudioElemRef.current.onpause = null;
        currentAudioElemRef.current.onended = null;
        currentAudioElemRef.current.onerror = null;
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
    setInterviewerAudioLevel(0);
  };

  const stopCandidateMedia = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    if (candidateStreamRef.current) {
      candidateStreamRef.current.getTracks().forEach((t) => t.stop());
      candidateStreamRef.current = null;
    }
    if (candidateAudioCtxRef.current && candidateAudioCtxRef.current.state !== "closed") {
      try {
        candidateAudioCtxRef.current.close();
      } catch (e) {}
      candidateAudioCtxRef.current = null;
    }
    setCandidateAudioLevel(0);
  };

  // Candidate camera setup
  const enableCandidateCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      candidateStreamRef.current = stream;
      if (candidateVideoRef.current) {
        candidateVideoRef.current.srcObject = stream;
      }
      setCameraActive(true);
      setHasPermission(true);
    } catch (err) {
      console.warn("Candidate camera unavailable or permission denied:", err);
      setHasPermission(false);
    }
  };

  const toggleCamera = () => {
    if (candidateStreamRef.current) {
      const videoTracks = candidateStreamRef.current.getVideoTracks();
      videoTracks.forEach((track) => {
        track.enabled = !cameraActive;
      });
      setCameraActive(!cameraActive);
    }
  };

  const toggleMic = () => {
    if (candidateStreamRef.current) {
      const audioTracks = candidateStreamRef.current.getAudioTracks();
      audioTracks.forEach((track) => {
        track.enabled = !micActive;
      });
      setMicActive(!micActive);
    }
  };

  /**
   * Synthesizes and plays AI speech.
   * STRICT AUDIO LIFECYCLE:
   * State is derived strictly from HTMLAudioElement onplay/onplaying/onended/onerror events.
   * No setTimeout timers are used to estimate audio completion.
   */
  const speakQuestion = async (text: string) => {
    try {
      stopAllAudio();
      setVoiceState("ai_responding");
      setErrorMessage(null);
      const t0 = performance.now();

      const token = getStoredToken();
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      const res = await fetch(`${baseUrl}/voice/tts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ text })
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
      audio.crossOrigin = "anonymous";
      currentAudioElemRef.current = audio;

      // Connect Web Audio API Analyser for real-time lip sync & visualizer
      try {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioCtx();
        ttsAudioCtxRef.current = ctx;
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 64;
        ttsAnalyserRef.current = analyser;

        const source = ctx.createMediaElementSource(audio);
        ttsSourceRef.current = source;
        source.connect(analyser);
        analyser.connect(ctx.destination);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateTTSVisualizer = () => {
          if (!ttsAnalyserRef.current || audio.paused || audio.ended) {
            setInterviewerAudioLevel(0);
            return;
          }
          ttsAnalyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          const bars: number[] = [];
          for (let i = 0; i < 7; i++) {
            const val = dataArray[i * 2] || 0;
            bars.push(Math.max(6, Math.round((val / 255) * 36)));
            sum += val;
          }
          setFrequencyBars(bars);
          const avg = sum / dataArray.length;
          const level = Math.min(100, Math.round((avg / 128) * 100));
          setInterviewerAudioLevel(level);

          ttsAnimFrameRef.current = requestAnimationFrame(updateTTSVisualizer);
        };

        // SPEAKING STATE triggers on actual audio play event
        audio.onplay = () => {
          setVoiceState("ai_speaking");
          if (ctx.state === "suspended") ctx.resume();
          updateTTSVisualizer();
        };

        audio.onplaying = () => {
          setVoiceState("ai_speaking");
        };
      } catch (audioCtxErr) {
        console.warn("Web Audio Context analyzer setup fallback:", audioCtxErr);
        audio.onplay = () => setVoiceState("ai_speaking");
        audio.onplaying = () => setVoiceState("ai_speaking");
      }

      // Start background microphone stream for barge-in detection while AI speaks
      startBargeInListener();

      // LISTENING STATE triggers ONLY when actual audio finishes or errors
      audio.onended = () => {
        setInterviewerAudioLevel(0);
        transitionToListening();
      };

      audio.onerror = (e) => {
        console.warn("Audio playback error:", e);
        setInterviewerAudioLevel(0);
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
      if (!candidateStreamRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false
        });
        candidateStreamRef.current = stream;
      }

      const stream = candidateStreamRef.current;
      setHasPermission(true);

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      candidateAudioCtxRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      candidateAnalyserRef.current = analyser;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      bargeInSpeechDurationRef.current = 0;
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const checkBargeIn = () => {
        if (!candidateAnalyserRef.current || !currentAudioElemRef.current) return;
        candidateAnalyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const level = Math.min(100, Math.round((avg / 128) * 100));
        setCandidateAudioLevel(level);

        if (level >= VAD_SPEECH_THRESHOLD) {
          bargeInSpeechDurationRef.current += 50;
          if (bargeInSpeechDurationRef.current >= BARGE_IN_TRIGGER_MS) {
            // Sustained meaningful candidate speech detected during AI speaking -> Trigger Barge-In
            console.log("Candidate Barge-In detected. Pausing AI audio.");
            stopAllAudio();
            setVoiceState("interrupted");
            transitionToListening(true);
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

      let stream = candidateStreamRef.current;
      if (!stream || stream.getAudioTracks().every((t) => t.readyState === "ended")) {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
        });
        candidateStreamRef.current = stream;
        if (candidateVideoRef.current) {
          candidateVideoRef.current.srcObject = stream;
        }
      }
      setHasPermission(true);

      if (!candidateAudioCtxRef.current || candidateAudioCtxRef.current.state === "closed") {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const audioCtx = new AudioCtx();
        candidateAudioCtxRef.current = audioCtx;
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 128;
        candidateAnalyserRef.current = analyser;
        const source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);
      }

      const analyser = candidateAnalyserRef.current!;
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
        if (!candidateAnalyserRef.current || mediaRecorder.state !== "recording") return;

        candidateAnalyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const level = Math.min(100, Math.round((avg / 128) * 100));
        setCandidateAudioLevel(level);

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
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: formData
      });

      if (!sttRes.ok) {
        throw new Error("Speech transcription failed.");
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

  // Unblock autoplay and resume audio playback upon user interaction
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
      {!consentGranted ? (
        <div
          className="saas-card"
          style={{
            padding: "3.5rem 2rem",
            backgroundColor: "#ffffff",
            borderRadius: "20px",
            border: "1px solid #e2e8f0",
            textAlign: "center",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.05)"
          }}
        >
          <div
            style={{
              backgroundColor: "#eef2ff",
              width: "68px",
              height: "68px",
              borderRadius: "50%",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "1.25rem"
            }}
          >
            <Video size={34} color="#4f46e5" />
          </div>

          <h2 style={{ fontSize: "1.5rem", fontWeight: 800, color: "#0f172a", marginBottom: "0.5rem" }}>
            Production AI Video Interview Room
          </h2>
          <p style={{ color: "#64748b", fontSize: "0.95rem", maxWidth: "620px", margin: "0 auto 1.75rem", lineHeight: 1.6 }}>
            You are about to enter a realistic simulated video interview conducted by an AI Executive Interviewer.
            The interviewer will ask questions aloud using natural speech synthesis and listen to your answers in real time.
          </p>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              background: "#f1f5f9",
              padding: "0.5rem 1rem",
              borderRadius: "9999px",
              fontSize: "0.82rem",
              color: "#475569",
              marginBottom: "2rem"
            }}
          >
            <ShieldCheck size={16} color="#059669" />
            <span>Camera & audio are processed securely in real time. No biometric data is stored.</span>
          </div>

          <div>
            <button
              onClick={() => setConsentGranted(true)}
              className="btn btn-primary"
              style={{
                padding: "0.85rem 2.5rem",
                fontSize: "1rem",
                borderRadius: "12px",
                boxShadow: "0 4px 14px rgba(79, 70, 229, 0.35)"
              }}
            >
              <Video size={18} /> Launch Video Interview Room
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Main Dual Video Stage */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.35fr 1fr",
              gap: "1.25rem",
              alignItems: "stretch"
            }}
          >
            {/* Left: AI Interviewer Video Stage */}
            <div
              className="saas-card"
              style={{
                position: "relative",
                height: "440px",
                backgroundColor: "#090d16",
                borderRadius: "18px",
                overflow: "hidden",
                border: "1px solid #1e293b",
                display: "flex",
                flexDirection: "column",
                boxShadow: "0 10px 30px rgba(0,0,0,0.25)"
              }}
            >
              {/* Interviewer Realistic Portrait with Dynamic Animation */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  overflow: "hidden"
                }}
              >
                <img
                  src={selectedPersona.avatarUrl}
                  alt={selectedPersona.name}
                  className={
                    voiceState === "ai_speaking"
                      ? "avatar-speaking"
                      : voiceState === "processing" || voiceState === "ai_responding"
                      ? "avatar-thinking"
                      : "avatar-breathing"
                  }
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    objectPosition: "center 20%",
                    transition: "transform 0.3s ease-out, filter 0.3s ease-out"
                  }}
                />

                {/* Ambient Gradient Overlays for Video Studio Look */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background:
                      "linear-gradient(180deg, rgba(15, 23, 42, 0.35) 0%, rgba(15, 23, 42, 0) 35%, rgba(15, 23, 42, 0.75) 100%)",
                    pointerEvents: "none"
                  }}
                />

                {/* Speaking Energy Radial Glow */}
                {voiceState === "ai_speaking" && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      boxShadow: "inset 0 0 50px rgba(99, 102, 241, 0.4)",
                      pointerEvents: "none",
                      transition: "box-shadow 0.2s ease"
                    }}
                  />
                )}
              </div>

              {/* Top Bar: Nameplate & Status Badge */}
              <div
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "1rem 1.25rem"
                }}
              >
                {/* Interviewer Metadata Nameplate */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.6rem",
                    backgroundColor: "rgba(15, 23, 42, 0.85)",
                    backdropFilter: "blur(8px)",
                    padding: "0.4rem 0.85rem",
                    borderRadius: "10px",
                    border: "1px solid rgba(255, 255, 255, 0.12)"
                  }}
                >
                  <div
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: voiceState === "ai_speaking" ? "#818cf8" : "#10b981"
                    }}
                  />
                  <div>
                    <div style={{ color: "#ffffff", fontSize: "0.85rem", fontWeight: 700, lineHeight: 1.2 }}>
                      {selectedPersona.name}
                    </div>
                    <div style={{ color: "#94a3b8", fontSize: "0.72rem" }}>
                      {selectedPersona.title}
                    </div>
                  </div>
                </div>

                {/* Dynamic State Badge */}
                <div>
                  {voiceState === "ai_speaking" && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(99, 102, 241, 0.9)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700,
                        boxShadow: "0 2px 8px rgba(99, 102, 241, 0.5)"
                      }}
                    >
                      <Volume2 size={14} className="spin" /> Speaking Question...
                    </span>
                  )}

                  {voiceState === "interrupted" && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(236, 72, 153, 0.9)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700
                      }}
                    >
                      <Zap size={14} /> Interrupted — Listening
                    </span>
                  )}

                  {(voiceState === "listening" || voiceState === "candidate_speaking") && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.45rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(16, 185, 129, 0.9)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700,
                        boxShadow: "0 2px 8px rgba(16, 185, 129, 0.4)"
                      }}
                    >
                      <span
                        className="listening-beacon"
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          backgroundColor: "#ffffff",
                          display: "inline-block"
                        }}
                      />
                      {voiceState === "candidate_speaking" ? "Candidate Speaking..." : "Listening..."}
                    </span>
                  )}

                  {(voiceState === "processing" || voiceState === "ai_responding") && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(245, 158, 11, 0.9)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700
                      }}
                    >
                      <Loader2 size={14} className="animate-spin" /> Thinking...
                    </span>
                  )}

                  {voiceState === "audio_blocked" && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(245, 158, 11, 0.95)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700
                      }}
                    >
                      <Play size={14} /> Enable Interviewer Audio
                    </span>
                  )}

                  {voiceState === "error" && (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.4rem",
                        padding: "0.35rem 0.85rem",
                        borderRadius: "9999px",
                        background: "rgba(239, 68, 68, 0.9)",
                        color: "#ffffff",
                        fontSize: "0.78rem",
                        fontWeight: 700
                      }}
                    >
                      <AlertCircle size={14} /> Reconnect
                    </span>
                  )}
                </div>
              </div>

              {/* Bottom Overlay: Audio-reactive Spectrum Visualizer & Persona Switcher */}
              <div
                style={{
                  position: "relative",
                  zIndex: 2,
                  marginTop: "auto",
                  padding: "1rem 1.25rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-end"
                }}
              >
                {/* Audio Visualizer Spectrum Bars (Active when AI speaks) */}
                <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "30px" }}>
                  {frequencyBars.map((height, idx) => (
                    <div
                      key={idx}
                      style={{
                        width: "5px",
                        height: voiceState === "ai_speaking" ? `${height}px` : "4px",
                        backgroundColor: voiceState === "ai_speaking" ? "#818cf8" : "rgba(255,255,255,0.2)",
                        borderRadius: "2px",
                        transition: "height 0.08s ease"
                      }}
                    />
                  ))}
                  <span style={{ fontSize: "0.72rem", color: "#cbd5e1", marginLeft: "0.4rem", fontWeight: 500 }}>
                    {voiceState === "ai_speaking" ? "ElevenLabs Voice Stream" : "Studio Audio Engine"}
                  </span>
                </div>

                {/* Persona Switcher Dropdown */}
                <div style={{ position: "relative" }}>
                  <button
                    onClick={() => setShowPersonaSelector(!showPersonaSelector)}
                    style={{
                      background: "rgba(15, 23, 42, 0.8)",
                      backdropFilter: "blur(8px)",
                      border: "1px solid rgba(255,255,255,0.15)",
                      color: "#ffffff",
                      fontSize: "0.75rem",
                      padding: "0.35rem 0.75rem",
                      borderRadius: "8px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.35rem"
                    }}
                  >
                    <UserCheck size={13} /> Switch Interviewer <ChevronDown size={12} />
                  </button>

                  {showPersonaSelector && (
                    <div
                      style={{
                        position: "absolute",
                        bottom: "100%",
                        right: 0,
                        marginBottom: "0.5rem",
                        backgroundColor: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: "10px",
                        padding: "0.4rem",
                        width: "220px",
                        boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
                        zIndex: 10
                      }}
                    >
                      {PERSONAS.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => {
                            setSelectedPersona(p);
                            setShowPersonaSelector(false);
                          }}
                          style={{
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            gap: "0.6rem",
                            padding: "0.5rem",
                            border: "none",
                            background: selectedPersona.id === p.id ? "rgba(99, 102, 241, 0.2)" : "transparent",
                            color: selectedPersona.id === p.id ? "#818cf8" : "#e2e8f0",
                            borderRadius: "6px",
                            cursor: "pointer",
                            textAlign: "left",
                            fontSize: "0.8rem"
                          }}
                        >
                          <img
                            src={p.avatarUrl}
                            alt={p.name}
                            style={{ width: "28px", height: "28px", borderRadius: "50%", objectFit: "cover" }}
                          />
                          <div>
                            <div style={{ fontWeight: 600 }}>{p.name}</div>
                            <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{p.badge}</div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Candidate Webcam Mirror Feed */}
            <div
              className="saas-card"
              style={{
                position: "relative",
                height: "440px",
                backgroundColor: "#020617",
                borderRadius: "18px",
                overflow: "hidden",
                border: "1px solid #1e293b",
                display: "flex",
                flexDirection: "column",
                boxShadow: "0 10px 30px rgba(0,0,0,0.25)"
              }}
            >
              {/* Live Webcam Stream */}
              <video
                ref={candidateVideoRef}
                autoPlay
                playsInline
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transform: "scaleX(-1)",
                  display: cameraActive ? "block" : "none"
                }}
              />

              {!cameraActive && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: "#0f172a",
                    color: "#64748b"
                  }}
                >
                  <CameraOff size={44} style={{ marginBottom: "0.75rem" }} />
                  <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Camera Disabled</span>
                </div>
              )}

              {/* Candidate Top Label */}
              <div
                style={{
                  position: "absolute",
                  top: "1rem",
                  left: "1.25rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  backgroundColor: "rgba(15, 23, 42, 0.85)",
                  backdropFilter: "blur(8px)",
                  padding: "0.4rem 0.85rem",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  color: "#ffffff",
                  fontSize: "0.82rem",
                  fontWeight: 600
                }}
              >
                <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#38bdf8" }} />
                <span>You (Candidate Feed)</span>
              </div>

              {/* Candidate Bottom Controls & Microphone Meter */}
              <div
                style={{
                  position: "absolute",
                  bottom: "1rem",
                  left: "1.25rem",
                  right: "1.25rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  backgroundColor: "rgba(15, 23, 42, 0.85)",
                  backdropFilter: "blur(8px)",
                  padding: "0.5rem 0.85rem",
                  borderRadius: "12px",
                  border: "1px solid rgba(255, 255, 255, 0.1)"
                }}
              >
                {/* Candidate Audio Level Indicator */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Mic size={14} color={candidateAudioLevel > 15 ? "#10b981" : "#94a3b8"} />
                  <div style={{ width: "60px", height: "5px", backgroundColor: "rgba(255,255,255,0.2)", borderRadius: "3px", overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${Math.min(100, candidateAudioLevel)}%`,
                        height: "100%",
                        backgroundColor: "#10b981",
                        transition: "width 0.08s ease"
                      }}
                    />
                  </div>
                  <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>{candidateAudioLevel}%</span>
                </div>

                {/* Audio / Video Toggles */}
                <div style={{ display: "flex", gap: "0.4rem" }}>
                  <button
                    onClick={toggleMic}
                    style={{
                      background: micActive ? "rgba(255,255,255,0.15)" : "#e11d48",
                      border: "none",
                      color: "#ffffff",
                      padding: "0.35rem 0.65rem",
                      borderRadius: "6px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center"
                    }}
                    title={micActive ? "Mute Microphone" : "Unmute Microphone"}
                  >
                    {micActive ? <Mic size={14} /> : <MicOff size={14} />}
                  </button>

                  <button
                    onClick={toggleCamera}
                    style={{
                      background: cameraActive ? "rgba(255,255,255,0.15)" : "#e11d48",
                      border: "none",
                      color: "#ffffff",
                      padding: "0.35rem 0.65rem",
                      borderRadius: "6px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center"
                    }}
                    title={cameraActive ? "Turn Off Camera" : "Turn On Camera"}
                  >
                    {cameraActive ? <Camera size={14} /> : <CameraOff size={14} />}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Active Question Box Overlay */}
          <div
            className="saas-card"
            style={{
              padding: "2rem",
              backgroundColor: "#ffffff",
              borderRadius: "16px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span
                style={{
                  fontSize: "0.82rem",
                  color: "#64748b",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  fontWeight: 600
                }}
              >
                Question #{questionNumber} • Difficulty:{" "}
                <strong style={{ color: "#4f46e5", textTransform: "capitalize" }}>{difficulty}</strong>
              </span>
              <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>
                {questionType}
              </span>
            </div>

            <h2
              style={{
                fontSize: "1.35rem",
                fontWeight: 700,
                color: "#0f172a",
                marginTop: "0.75rem",
                lineHeight: 1.5
              }}
            >
              &ldquo;{currentQuestionText}&rdquo;
            </h2>

            {expectedConcepts && expectedConcepts.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "1rem" }}>
                {expectedConcepts.map((c) => (
                  <span key={c} className="badge badge-primary" style={{ fontSize: "0.75rem" }}>
                    Focus: {c}
                  </span>
                ))}
              </div>
            )}

            {/* Action Bar with Voice & Video Lifecycle Controls */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "0.75rem",
                marginTop: "1.5rem",
                paddingTop: "1.25rem",
                borderTop: "1px solid #f1f5f9"
              }}
            >
              {voiceState === "audio_blocked" && (
                <button
                  onClick={handleUnblockAudio}
                  className="btn btn-primary"
                  style={{
                    background: "#6366f1",
                    padding: "0.65rem 1.5rem",
                    fontSize: "0.9rem",
                    borderRadius: "10px"
                  }}
                >
                  <Play size={16} /> Enable Interviewer Audio
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
                      padding: "0.65rem 1.5rem",
                      fontSize: "0.9rem",
                      borderRadius: "10px",
                      boxShadow: "0 4px 12px rgba(16, 185, 129, 0.25)"
                    }}
                  >
                    <Square size={16} /> Finish Speaking
                  </button>

                  <button
                    onClick={handleReplayQuestion}
                    className="btn btn-secondary"
                    style={{ padding: "0.65rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                  >
                    <RotateCcw size={15} /> Replay Question (🔊)
                  </button>
                </>
              )}

              {voiceState === "ai_speaking" && (
                <button
                  onClick={() => {
                    stopAllAudio();
                    transitionToListening(true);
                  }}
                  className="btn btn-secondary"
                  style={{ padding: "0.55rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
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
                    style={{ padding: "0.65rem 1.5rem", fontSize: "0.9rem", borderRadius: "10px" }}
                  >
                    <RefreshCw size={16} /> Retry Speaking
                  </button>

                  <button
                    onClick={handleReplayQuestion}
                    className="btn btn-secondary"
                    style={{ padding: "0.65rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                  >
                    <RotateCcw size={15} /> Replay Question (🔊)
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Error / Attention Notice */}
          {errorMessage && (
            <div
              className="saas-card"
              style={{
                padding: "1rem 1.25rem",
                backgroundColor: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: "12px",
                color: "#e11d48",
                fontSize: "0.88rem",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem"
              }}
            >
              <AlertCircle size={18} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Recognized Speech Transcript Display */}
          {spokenTranscript && (
            <div
              className="saas-card"
              style={{
                padding: "1.25rem 1.5rem",
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "14px"
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
                borderRadius: "14px"
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
        </>
      )}
    </div>
  );
};
