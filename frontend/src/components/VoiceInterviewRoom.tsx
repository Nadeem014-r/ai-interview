"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Square,
  Play,
  RotateCcw,
  Zap,
  Radio
} from "lucide-react";
import { getStoredToken } from "@/lib/auth";

// Standard 16kHz mono WAV encoder for zero-dependency universal speech decoding
function encodePCMToWAV(samples: Float32Array, sampleRate: number = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // Mono channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // Byte rate
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // 16-bit
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function downsamplePCMBuffer(buffer: Float32Array, inputSampleRate: number, outputSampleRate: number = 16000): Float32Array {
  if (inputSampleRate === outputSampleRate) return buffer;
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

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
  isConcluding?: boolean;
  onConclusionFinished?: () => void;
}

type RealtimeVoiceState =
  | "idle"
  | "tts_loading"
  | "ai_speaking"
  | "listening"
  | "candidate_speaking"
  | "interrupted"
  | "processing"
  | "audio_blocked"
  | "error";

const VAD_SPEECH_THRESHOLD = 15;
const VAD_SILENCE_TIMEOUT_MS = 2800;
const VAD_MIN_SPEECH_DURATION_MS = 1200;
const BARGE_IN_TRIGGER_MS = 400;

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
  isConcluding = false,
  onConclusionFinished
}) => {
  const [voiceState, setVoiceState] = useState<RealtimeVoiceState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [spokenTranscript, setSpokenTranscript] = useState<string>("");
  const [latencyMetrics, setLatencyMetrics] = useState<{ ttsMs?: number; sttMs?: number; totalMs?: number }>({});
  const [activeSubtitleText, setActiveSubtitleText] = useState<string>(currentQuestionText || "");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const lastSpokenQuestionRef = useRef<string>("");

  // SINGLE-AUDIO-OWNER CONTROLLER & PROMISE REFS
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const cachedAudioMapRef = useRef<{ [text: string]: string }>({});
  const ttsFetchPromiseMapRef = useRef<{ [text: string]: Promise<string | null> }>({});

  // VAD & Barge-in Tracking Refs
  const speechStartTimeRef = useRef<number>(0);
  const totalSpeechDurationMsRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const bargeInSpeechDurationRef = useRef<number>(0);
  const turnStartTimeRef = useRef<number>(0);

  // Clean up any ongoing interviewer audio
  const stopCurrentInterviewerAudio = () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    if (currentAudioRef.current) {
      try {
        currentAudioRef.current.onplay = null;
        currentAudioRef.current.onplaying = null;
        currentAudioRef.current.onpause = null;
        currentAudioRef.current.onended = null;
        currentAudioRef.current.onerror = null;
        currentAudioRef.current.pause();
        currentAudioRef.current.currentTime = 0;
        currentAudioRef.current.src = "";
      } catch (e) {}
      currentAudioRef.current = null;
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

  useEffect(() => {
    return () => {
      stopCurrentInterviewerAudio();
      stopMicrophone();
      Object.values(cachedAudioMapRef.current).forEach((url) => {
        try {
          URL.revokeObjectURL(url);
        } catch (e) {}
      });
      cachedAudioMapRef.current = {};
      ttsFetchPromiseMapRef.current = {};
    };
  }, []);

  // Fetch or retrieve cached Kokoro TTS audio with in-flight deduplication
  // Fetch or retrieve cached Kokoro TTS audio with in-flight deduplication
  const fetchTTSAudio = async (text: string): Promise<string | null> => {
    if (!text || !text.trim()) return null;
    if (typeof window !== "undefined" && (window as any).__TTS_AUDIO_CACHE__?.[text]) {
      return (window as any).__TTS_AUDIO_CACHE__[text];
    }
    if (cachedAudioMapRef.current[text]) {
      return cachedAudioMapRef.current[text];
    }
    if (ttsFetchPromiseMapRef.current[text]) {
      return ttsFetchPromiseMapRef.current[text];
    }

    const promise = (async () => {
      try {
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
        if (res.ok) {
          const audioBlob = await res.blob();
          if (audioBlob && audioBlob.size > 0) {
            const audioUrl = URL.createObjectURL(audioBlob);
            cachedAudioMapRef.current[text] = audioUrl;
            if (typeof window !== "undefined") {
              (window as any).__TTS_AUDIO_CACHE__ = (window as any).__TTS_AUDIO_CACHE__ || {};
              (window as any).__TTS_AUDIO_CACHE__[text] = audioUrl;
            }
            return audioUrl;
          }
        }
        return null;
      } catch (e) {
        console.warn("Kokoro TTS synthesis error:", e);
        return null;
      } finally {
        delete ttsFetchPromiseMapRef.current[text];
      }
    })();

    ttsFetchPromiseMapRef.current[text] = promise;
    return promise;
  };

  // Play audio url via single audio owner controller
  const playAudioUrl = async (audioUrl: string, text: string) => {
    stopCurrentInterviewerAudio();

    const audio = new Audio(audioUrl);
    currentAudioRef.current = audio;

    audio.onplay = () => {
      setActiveSubtitleText(text);
      setVoiceState("ai_speaking");
    };

    audio.onplaying = () => {
      setActiveSubtitleText(text);
      setVoiceState("ai_speaking");
    };

    audio.onended = () => {
      if (isConcluding) {
        onConclusionFinished?.();
      } else {
        transitionToListening();
      }
    };

    audio.onerror = (e) => {
      console.warn("Audio playback error, falling back to Web Speech API:", e);
      speakWithBrowserSpeech(text);
    };

    try {
      setVoiceState("ai_speaking");
      await audio.play();
      if (!isConcluding) {
        startBargeInListener();
      }
    } catch (playErr: unknown) {
      console.warn("Audio play rejected, attempting browser speech synthesis:", playErr);
      speakWithBrowserSpeech(text);
    }
  };

  // Synthesize and play AI speech via Kokoro with caching and immediate speech
  const speakQuestion = async (text: string) => {
    if (!text || !text.trim()) return;

    const cachedUrl = (typeof window !== "undefined" && (window as any).__TTS_AUDIO_CACHE__?.[text]) || cachedAudioMapRef.current[text];
    if (cachedUrl) {
      await playAudioUrl(cachedUrl, text);
      return;
    }

    try {
      stopCurrentInterviewerAudio();
      setVoiceState("ai_speaking");
      setErrorMessage(null);

      // Start browser speech immediately so there is ZERO delay or loading spinner
      speakWithBrowserSpeech(text);

      // Background cache Kokoro audio for subsequent turns/replays
      fetchTTSAudio(text);
    } catch (err) {
      console.warn("TTS synthesis error:", err);
      speakWithBrowserSpeech(text);
    }
  };

  // Automatically speak active question ONCE when it becomes active
  useEffect(() => {
    if (currentQuestionText && currentQuestionText.trim() && currentQuestionText !== lastSpokenQuestionRef.current) {
      lastSpokenQuestionRef.current = currentQuestionText;
      setActiveSubtitleText(currentQuestionText);
      speakQuestion(currentQuestionText);
    }
  }, [currentQuestionText]);

  // Browser Native Web Speech API fallback
  const speakWithBrowserSpeech = (text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      if (isConcluding) {
        onConclusionFinished?.();
      } else {
        transitionToListening();
      }
      return;
    }

    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      const getBestVoice = () => {
        const voices = window.speechSynthesis.getVoices();
        return (
          voices.find(
            (v) =>
              v.lang.startsWith("en") &&
              (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("Neural"))
          ) || voices.find((v) => v.lang.startsWith("en"))
        );
      };

      const preferredVoice = getBestVoice();
      if (preferredVoice) utterance.voice = preferredVoice;

      utterance.onstart = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
        if (!isConcluding) startBargeInListener();
      };

      utterance.onend = () => {
        if (isConcluding) {
          onConclusionFinished?.();
        } else {
          transitionToListening();
        }
      };

      utterance.onerror = () => {
        if (isConcluding) {
          onConclusionFinished?.();
        } else {
          transitionToListening();
        }
      };

      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("Web Speech API error:", e);
      if (isConcluding) {
        onConclusionFinished?.();
      } else {
        transitionToListening();
      }
    }
  };

  // Background microphone to monitor for candidate barge-in during AI speaking
  const startBargeInListener = async () => {
    try {
      if (!streamRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false
        });
        streamRef.current = stream;
      }

      const stream = streamRef.current;
      if (!stream) return;

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      let lastCheck = performance.now();

      const checkBargeIn = () => {
        if (!analyserRef.current || currentAudioRef.current === null) return;

        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const avg = sum / bufferLength;
        const currentLevel = Math.min(100, Math.round((avg / 128) * 100));

        setAudioLevel(currentLevel);
        const now = performance.now();
        const delta = now - lastCheck;
        lastCheck = now;

        if (currentLevel > VAD_SPEECH_THRESHOLD + 10) {
          bargeInSpeechDurationRef.current += delta;
          if (bargeInSpeechDurationRef.current >= BARGE_IN_TRIGGER_MS) {
            stopCurrentInterviewerAudio();
            if (typeof window !== "undefined" && "speechSynthesis" in window) {
              window.speechSynthesis.cancel();
            }
            transitionToListening(true);
            return;
          }
        } else {
          bargeInSpeechDurationRef.current = Math.max(0, bargeInSpeechDurationRef.current - delta * 2);
        }

        animationFrameRef.current = requestAnimationFrame(checkBargeIn);
      };

      checkBargeIn();
    } catch (err) {
      console.warn("Barge-in listener setup warning:", err);
    }
  };

  // Transition from AI speaking to candidate listening with microphone recording
  const transitionToListening = (isInterrupted = false) => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    setVoiceState(isInterrupted ? "interrupted" : "listening");
    startCandidateMicrophone();
  };

  // Start active MediaRecorder for candidate answer turn
  const startCandidateMicrophone = async () => {
    try {
      if (!streamRef.current) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false
        });
        streamRef.current = stream;
      }

      const stream = streamRef.current;
      if (!stream) throw new Error("No media stream available.");

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      // Collect raw PCM samples for guaranteed standard 16kHz WAV generation
      pcmChunksRef.current = [];
      try {
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);
        processorNodeRef.current = processor;
        processor.onaudioprocess = (e) => {
          if (mediaRecorderRef.current?.state === "recording") {
            const inputData = e.inputBuffer.getChannelData(0);
            pcmChunksRef.current.push(new Float32Array(inputData));
          }
        };
        source.connect(processor);
        processor.connect(audioCtx.destination);
      } catch (procErr) {
        console.warn("ScriptProcessor initialization fallback:", procErr);
      }

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/ogg")
        ? "audio/ogg"
        : "";

      const options = mimeType ? { mimeType } : undefined;
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        let completeBlob: Blob;
        if (pcmChunksRef.current.length > 0) {
          const totalLength = pcmChunksRef.current.reduce((acc, chunk) => acc + chunk.length, 0);
          const merged = new Float32Array(totalLength);
          let offset = 0;
          for (const chunk of pcmChunksRef.current) {
            merged.set(chunk, offset);
            offset += chunk.length;
          }
          const downsampled = downsamplePCMBuffer(merged, audioCtx.sampleRate, 16000);
          completeBlob = encodePCMToWAV(downsampled, 16000);
        } else {
          const finalMime = mimeType || "audio/webm";
          completeBlob = new Blob(audioChunksRef.current, { type: finalMime });
        }
        handleAudioCaptured(completeBlob);
      };

      recorder.start(250);

      speechStartTimeRef.current = 0;
      totalSpeechDurationMsRef.current = 0;
      lastSpeechTimeRef.current = performance.now();
      turnStartTimeRef.current = performance.now();

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      let lastLoopTime = performance.now();

      const vadLoop = () => {
        if (!analyserRef.current || mediaRecorderRef.current?.state !== "recording") return;

        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const avg = sum / bufferLength;
        const currentLevel = Math.min(100, Math.round((avg / 128) * 100));

        setAudioLevel(currentLevel);
        const now = performance.now();
        const delta = now - lastLoopTime;
        lastLoopTime = now;

        const isSpeaking = currentLevel >= VAD_SPEECH_THRESHOLD;

        if (isSpeaking) {
          lastSpeechTimeRef.current = now;
          if (speechStartTimeRef.current === 0) {
            speechStartTimeRef.current = now;
            setVoiceState("candidate_speaking");
          }
          totalSpeechDurationMsRef.current += delta;
        } else {
          if (totalSpeechDurationMsRef.current >= VAD_MIN_SPEECH_DURATION_MS) {
            const silenceDuration = now - lastSpeechTimeRef.current;
            if (silenceDuration >= VAD_SILENCE_TIMEOUT_MS) {
              finishSpeaking();
              return;
            }
          }
        }

        if (now - turnStartTimeRef.current > 120000) {
          finishSpeaking();
          return;
        }

        animationFrameRef.current = requestAnimationFrame(vadLoop);
      };

      vadLoop();
    } catch (err) {
      console.error("Microphone activation error:", err);
      setVoiceState("error");
      setErrorMessage("Microphone access denied or unavailable. Please grant microphone permissions.");
    }
  };

  // Candidate finishes speaking
  const finishSpeaking = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      setVoiceState("processing");
      mediaRecorderRef.current.stop();
      if (processorNodeRef.current) {
        try {
          processorNodeRef.current.disconnect();
        } catch (e) {}
        processorNodeRef.current = null;
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    }
  };

  // Process captured audio through STT and submit candidate transcript
  const handleAudioCaptured = async (audioBlob: Blob) => {
    try {
      setVoiceState("processing");
      const t0 = performance.now();
      const token = getStoredToken();
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

      const formData = new FormData();
      const filename = audioBlob.type.includes("wav")
        ? "answer_turn.wav"
        : audioBlob.type.includes("ogg")
        ? "answer_turn.ogg"
        : "answer_turn.webm";
      formData.append("file", audioBlob, filename);

      const sttRes = await fetch(`${baseUrl}/voice/stt`, {
        method: "POST",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: formData
      });

      if (!sttRes.ok) {
        const errorJson = await sttRes.json().catch(() => null);
        const detail = errorJson?.detail || "Speech transcription failed.";
        throw new Error(detail);
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

      await onAnswerSubmitted(transcript, audioUrl);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to process speech";
      setVoiceState("error");
      setErrorMessage(errorMsg || "An error occurred while processing speech. Click below to retry speaking.");
    }
  };

  const handleUnblockAudio = async () => {
    try {
      if (audioContextRef.current && audioContextRef.current.state === "suspended") {
        await audioContextRef.current.resume();
      }
    } catch (e) {}

    if (currentAudioRef.current && currentAudioRef.current.src) {
      try {
        setVoiceState("ai_speaking");
        await currentAudioRef.current.play();
      } catch (err) {
        if (currentQuestionText) {
          speakQuestion(currentQuestionText);
        } else {
          transitionToListening();
        }
      }
    } else if (currentQuestionText) {
      speakQuestion(currentQuestionText);
    }
  };

  // Replay question audio via Single Audio Owner without altering interview state
  const handleListenAgain = () => {
    if (submitting || voiceState === "processing" || voiceState === "tts_loading") return;

    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      try {
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    stopCurrentInterviewerAudio();
    speakQuestion(currentQuestionText);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", marginBottom: "1.5rem" }}>
      {/* Main Voice Interactive Card */}
      <div
        className="saas-card"
        style={{
              padding: "2.5rem 2rem",
              backgroundColor: "#0f172a",
              borderRadius: "20px",
              color: "#ffffff",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              position: "relative",
              overflow: "hidden",
              border: "1px solid #1e293b",
              boxShadow: "0 10px 30px rgba(0,0,0,0.3)"
            }}
          >
            {/* Top Status Header */}
            <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    backgroundColor: voiceState === "ai_speaking" ? "#818cf8" : "#10b981"
                  }}
                />
                <span style={{ fontSize: "0.85rem", color: "#94a3b8", fontWeight: 600 }}>
                  Voice Interview Session
                </span>
              </div>

              {/* State Status Badge */}
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
                    fontWeight: 700
                  }}
                >
                  <Volume2 size={14} className="spin" /> Interviewer Speaking...
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
                    fontWeight: 700
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

              {voiceState === "processing" && (
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
                  <Loader2 size={14} className="animate-spin" /> Evaluating Answer...
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
                marginBottom: "1.75rem"
              }}
            >
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
                      : "radial-gradient(circle, rgba(148,163,184,0.3) 0%, rgba(148,163,184,0) 70%)",
                  transform: `scale(${1 + (audioLevel / 100) * 0.45})`,
                  transition: "transform 0.08s ease-out"
                }}
              />

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
                      : "linear-gradient(135deg, #475569 0%, #1e293b 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 0 30px rgba(99, 102, 241, 0.5)",
                  zIndex: 2
                }}
              >
                {voiceState === "ai_speaking" && <Volume2 size={36} color="#ffffff" />}
                {voiceState === "audio_blocked" && <Play size={36} color="#ffffff" />}
                {(voiceState === "listening" || voiceState === "candidate_speaking") && (
                  <Mic size={36} color="#ffffff" />
                )}
                {(voiceState === "processing" || voiceState === "tts_loading") && (
                  <Loader2 size={36} color="#ffffff" className="animate-spin" />
                )}
                {voiceState === "error" && <MicOff size={36} color="#fca5a5" />}
                {voiceState === "idle" && <Sparkles size={36} color="#cbd5e1" />}
              </div>
            </div>

            {/* Conversational Interviewer Subtitle (Visible during speech) */}
            {activeSubtitleText && (
              <div
                style={{
                  maxWidth: "760px",
                  width: "100%",
                  margin: "0 auto",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  backdropFilter: "blur(10px)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: "14px",
                  padding: "1.25rem 1.75rem",
                  textAlign: "center"
                }}
              >
                <div
                  style={{
                    fontSize: "0.78rem",
                    color: "#818cf8",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    fontWeight: 700,
                    marginBottom: "0.4rem"
                  }}
                >
                  Interviewer
                </div>
                <p
                  style={{
                    fontSize: "1.15rem",
                    fontWeight: 500,
                    color: "#f8fafc",
                    lineHeight: 1.6,
                    margin: 0
                  }}
                >
                  &ldquo;{activeSubtitleText}&rdquo;
                </p>
              </div>
            )}

            {/* Live Audio Level Bar */}
            {(voiceState === "listening" || voiceState === "candidate_speaking") && (
              <div style={{ width: "100%", maxWidth: "320px", marginTop: "1.5rem" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "0.75rem",
                    color: "#6ee7b7",
                    marginBottom: "0.3rem"
                  }}
                >
                  <span>Microphone Live</span>
                  <span>{audioLevel}%</span>
                </div>
                <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.max(5, audioLevel)}%`,
                      background: voiceState === "candidate_speaking" ? "#10b981" : "#34d399",
                      transition: "width 0.08s ease-out"
                    }}
                  />
                </div>
              </div>
            )}

            {/* Action Controls */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                justifyContent: "center",
                gap: "1rem",
                marginTop: "2rem"
              }}
            >
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
                    boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)"
                  }}
                >
                  <Play size={18} /> Start Interview
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
                      boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)"
                    }}
                  >
                    <Square size={18} /> Finish Speaking
                  </button>

                  <button
                    onClick={handleListenAgain}
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
                      gap: "0.4rem"
                    }}
                  >
                    <RotateCcw size={16} /> Listen Again
                  </button>
                </>
              )}

              {voiceState === "ai_speaking" && (
                <>
                  <button
                    onClick={() => {
                      stopCurrentInterviewerAudio();
                      transitionToListening(true);
                    }}
                    style={{
                      background: "rgba(255, 255, 255, 0.15)",
                      border: "1px solid rgba(255, 255, 255, 0.3)",
                      color: "#ffffff",
                      padding: "0.5rem 1.25rem",
                      borderRadius: "10px",
                      fontSize: "0.85rem",
                      cursor: "pointer"
                    }}
                  >
                    Start Answer
                  </button>

                  <button
                    onClick={handleListenAgain}
                    style={{
                      background: "rgba(255, 255, 255, 0.15)",
                      border: "1px solid rgba(255, 255, 255, 0.3)",
                      color: "#ffffff",
                      padding: "0.5rem 1.25rem",
                      borderRadius: "10px",
                      fontSize: "0.85rem",
                      cursor: "pointer"
                    }}
                  >
                    <RotateCcw size={14} style={{ display: "inline", marginRight: "4px" }} /> Listen Again
                  </button>
                </>
              )}

              {(voiceState === "error" || voiceState === "idle" || voiceState === "tts_loading") && (
                <>
                  <button
                    onClick={() => transitionToListening()}
                    disabled={submitting || voiceState === "tts_loading"}
                    className="btn btn-primary"
                    style={{
                      background: "#6366f1",
                      padding: "0.75rem 1.75rem",
                      fontSize: "0.95rem",
                      borderRadius: "12px",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem"
                    }}
                  >
                    <RefreshCw size={18} /> Retry Speaking
                  </button>

                  <button
                    onClick={handleListenAgain}
                    disabled={voiceState === "tts_loading"}
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
                      gap: "0.4rem"
                    }}
                  >
                    <RotateCcw size={16} /> Listen Again
                  </button>
                </>
              )}
            </div>

            {/* Error Notice */}
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
                  maxWidth: "600px"
                }}
              >
                {errorMessage}
              </div>
            )}
          </div>

      {/* Candidate Response Transcript */}
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
          <div
            style={{
              fontSize: "0.78rem",
              color: "#059669",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              fontWeight: 700,
              marginBottom: "0.35rem"
            }}
          >
            You
          </div>
          <p style={{ color: "#0f172a", fontSize: "1.05rem", lineHeight: 1.5, margin: 0 }}>
            &ldquo;{spokenTranscript}&rdquo;
          </p>
        </div>
      )}
    </div>
  );
};
