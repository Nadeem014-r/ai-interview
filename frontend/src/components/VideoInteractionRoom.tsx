"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  MicOff,
  Camera,
  CameraOff,
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
  Video
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

interface VideoInteractionRoomProps {
  interviewId: number;
  currentQuestionText: string;
  questionNumber: number;
  difficulty: string;
  questionType: string;
  expectedConcepts?: string[];
  onAnswerSubmitted: (transcript: string, audioUrl?: string) => Promise<void>;
  submitting: boolean;
  companyName?: string;
  roleTitle?: string;
  isConcluding?: boolean;
  onConclusionFinished?: () => void;
}

// Transcription and evaluation are two distinct waits with very different
// causes -- local Whisper decoding first, then two sequential LLM calls on the
// server. Labelling both "Analyzing your response" described work that had not
// started yet, so each phase now names itself.
type ProcessingPhase = "transcribing" | "evaluating";

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

export const VideoInteractionRoom: React.FC<VideoInteractionRoomProps> = ({
  interviewId,
  currentQuestionText,
  questionNumber,
  difficulty,
  questionType,
  expectedConcepts = [],
  onAnswerSubmitted,
  submitting,
  companyName = "TechCorp",
  roleTitle = "Software Engineer",
  isConcluding = false,
  onConclusionFinished
}) => {
  const [voiceState, setVoiceState] = useState<RealtimeVoiceState>("idle");
  const [processingPhase, setProcessingPhase] = useState<ProcessingPhase>("transcribing");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState<boolean>(true);
  const [micActive, setMicActive] = useState<boolean>(true);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [candidateAudioLevel, setCandidateAudioLevel] = useState<number>(0);
  const [interviewerAudioLevel, setInterviewerAudioLevel] = useState<number>(0);
  const [frequencyBars, setFrequencyBars] = useState<number[]>([12, 18, 28, 36, 24, 16, 8]);
  const [latencyMetrics, setLatencyMetrics] = useState<{ ttsMs?: number; sttMs?: number; totalMs?: number }>({});
  const [activeSubtitleText, setActiveSubtitleText] = useState<string>(currentQuestionText || "");

  // Media & Web Audio references
  const candidateVideoRef = useRef<HTMLVideoElement | null>(null);
  const candidateStreamRef = useRef<MediaStream | null>(null);
  const candidateAudioCtxRef = useRef<AudioContext | null>(null);
  const candidateAnalyserRef = useRef<AnalyserNode | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastSpokenQuestionRef = useRef<string>("");

  // SINGLE-AUDIO-OWNER CONTROLLER & PROMISE REFS
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const cachedAudioMapRef = useRef<{ [text: string]: string }>({});
  const ttsFetchPromiseMapRef = useRef<{ [text: string]: Promise<string | null> }>({});

  // Web Audio Context for Interviewer TTS
  const ttsAudioCtxRef = useRef<AudioContext | null>(null);
  const ttsAnalyserRef = useRef<AnalyserNode | null>(null);
  const ttsSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const ttsAnimFrameRef = useRef<number | null>(null);

  // VAD & Barge-in Tracking Refs
  const speechStartTimeRef = useRef<number>(0);
  const totalSpeechDurationMsRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const bargeInSpeechDurationRef = useRef<number>(0);
  const turnStartTimeRef = useRef<number>(0);

  // Stop and clean up any currently playing interviewer audio (Single Audio Owner)
  const stopCurrentInterviewerAudio = () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    if (ttsAnimFrameRef.current) {
      cancelAnimationFrame(ttsAnimFrameRef.current);
      ttsAnimFrameRef.current = null;
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

  useEffect(() => {
    return () => {
      stopCurrentInterviewerAudio();
      stopCandidateMedia();
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

  // Candidate camera setup & stream attachment
  const enableCandidateCamera = async (): Promise<MediaStream | null> => {
    try {
      if (candidateStreamRef.current && candidateStreamRef.current.active) {
        const hasVideo = candidateStreamRef.current.getVideoTracks().length > 0;
        const hasAudio = candidateStreamRef.current.getAudioTracks().length > 0;
        if (hasVideo && hasAudio) {
          if (candidateVideoRef.current) {
            candidateVideoRef.current.srcObject = candidateStreamRef.current;
            candidateVideoRef.current.play().catch(() => {});
          }
          setCameraActive(true);
          setHasPermission(true);
          return candidateStreamRef.current;
        }
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      candidateStreamRef.current = stream;
      if (candidateVideoRef.current) {
        candidateVideoRef.current.srcObject = stream;
        candidateVideoRef.current.play().catch(() => {});
      }
      setCameraActive(true);
      setHasPermission(true);
      return stream;
    } catch (err) {
      console.warn("Candidate camera unavailable or permission denied:", err);
      try {
        const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        candidateStreamRef.current = fallbackStream;
        if (candidateVideoRef.current) {
          candidateVideoRef.current.srcObject = fallbackStream;
          candidateVideoRef.current.play().catch(() => {});
        }
        setCameraActive(true);
        setHasPermission(true);
        return fallbackStream;
      } catch (fallbackErr) {
        setHasPermission(false);
        return null;
      }
    }
  };

  // Initialize camera and mirror feed on mount
  useEffect(() => {
    enableCandidateCamera();
  }, []);

  // Bug Fix 5a: Re-attach stream srcObject whenever permission is granted or
  // cameraActive changes — ensures the video element is populated even if the
  // ref was not yet mounted when getUserMedia first resolved.
  useEffect(() => {
    if (
      candidateVideoRef.current &&
      candidateStreamRef.current &&
      candidateStreamRef.current.active
    ) {
      if (candidateVideoRef.current.srcObject !== candidateStreamRef.current) {
        candidateVideoRef.current.srcObject = candidateStreamRef.current;
      }
      candidateVideoRef.current.play().catch(() => {});
    }
  }, [hasPermission, cameraActive]);

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

  // Play audio url via single audio owner controller
  const playAudioUrl = async (audioUrl: string, text: string) => {
    stopCurrentInterviewerAudio();

    const audio = new Audio(audioUrl);
    currentAudioRef.current = audio;

    // Connect Web Audio API Analyser for real-time lip sync & visualizer
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!ttsAudioCtxRef.current || ttsAudioCtxRef.current.state === "closed") {
        ttsAudioCtxRef.current = new AudioCtx();
      }
      const ctx = ttsAudioCtxRef.current;
      if (ctx.state === "suspended") {
        await ctx.resume();
      }

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
        const avg = sum / (dataArray.length || 1);
        const level = Math.min(100, Math.round((avg / 128) * 100));
        setInterviewerAudioLevel(level);

        ttsAnimFrameRef.current = requestAnimationFrame(updateTTSVisualizer);
      };

      audio.onplay = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
        if (ctx.state === "suspended") ctx.resume();
        updateTTSVisualizer();
      };

      audio.onplaying = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
      };
    } catch (audioCtxErr) {
      console.warn("Web Audio Context analyser setup:", audioCtxErr);
      audio.onplay = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
      };
      audio.onplaying = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
      };
    }

    audio.onended = () => {
      setInterviewerAudioLevel(0);
      if (isConcluding) {
        onConclusionFinished?.();
      } else {
        transitionToListening();
      }
    };

    audio.onerror = (e) => {
      console.warn("Audio playback error, falling back to speech synthesis:", e);
      setInterviewerAudioLevel(0);
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

  // Synthesize and play AI speech via Kokoro 0.9.4 with audio caching and immediate speech
  const speakQuestion = async (text: string) => {
    if (!text || !text.trim()) return;

    const cachedUrl = (typeof window !== "undefined" && (window as any).__TTS_AUDIO_CACHE__?.[text]) || cachedAudioMapRef.current[text];
    if (cachedUrl) {
      await playAudioUrl(cachedUrl, text);
      return;
    }

    // ONE voice owns the whole session. Starting browser speech immediately
    // while Kokoro was fetched only for the cache meant the first question
    // (pre-warmed Kokoro, female) and every later question (Windows SAPI,
    // male by default) were spoken by different voices. Server TTS is now
    // always awaited; the browser synthesiser is a real failure path only.
    stopCurrentInterviewerAudio();
    setErrorMessage(null);
    // Show the line straight away so the wait for audio reads as a pause.
    setActiveSubtitleText(text);
    setVoiceState("tts_loading");

    try {
      const audioUrl = await fetchTTSAudio(text);
      if (audioUrl) {
        await playAudioUrl(audioUrl, text);
        return;
      }
    } catch (err) {
      console.warn("Interviewer TTS synthesis failed, using browser speech:", err);
    }

    speakWithBrowserSpeech(text);
  };

  // Automatically speak active question ONCE when it becomes active
  useEffect(() => {
    if (currentQuestionText && currentQuestionText.trim() && currentQuestionText !== lastSpokenQuestionRef.current) {
      lastSpokenQuestionRef.current = currentQuestionText;
      setActiveSubtitleText(currentQuestionText);
      speakQuestion(currentQuestionText);
    }
  }, [currentQuestionText]);

  // Chrome returns [] from getVoices() on the first call, so the opening line
  // was spoken by the OS default (male on Windows) and later lines by whatever
  // the loaded list offered. Pinning one voice for the session, and priming the
  // list when it arrives, keeps the interviewer sounding like one person.
  const pinnedVoiceRef = useRef<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const prime = () => {
      pinnedVoiceRef.current = null;
      resolveBrowserVoice();
    };
    prime();
    window.speechSynthesis.addEventListener?.("voiceschanged", prime);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", prime);
  }, []);

  // Kokoro's interviewer voice (af_heart) is female, so the fallback prefers a
  // female English voice: dropping to it changes audio quality, not the person.
  const resolveBrowserVoice = (): SpeechSynthesisVoice | null => {
    if (pinnedVoiceRef.current) return pinnedVoiceRef.current;
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;

    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    const english = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("en"));
    if (english.length === 0) return null;

    const FEMALE_HINTS = ["zira", "aria", "jenny", "michelle", "samantha", "female", "eva", "libby", "sonia"];
    const isFemale = (v: SpeechSynthesisVoice) =>
      FEMALE_HINTS.some((h) => v.name.toLowerCase().includes(h));
    const isHighQuality = (v: SpeechSynthesisVoice) => /natural|neural|google/i.test(v.name);

    const chosen =
      english.find((v) => isFemale(v) && isHighQuality(v)) ||
      english.find(isFemale) ||
      english.find(isHighQuality) ||
      english[0];

    pinnedVoiceRef.current = chosen || null;
    return pinnedVoiceRef.current;
  };

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

      const preferredVoice = resolveBrowserVoice();
      if (preferredVoice) utterance.voice = preferredVoice;

      utterance.onstart = () => {
        setActiveSubtitleText(text);
        setVoiceState("ai_speaking");
        if (!isConcluding) startBargeInListener();
      };

      utterance.onend = () => {
        setInterviewerAudioLevel(0);
        if (isConcluding) {
          onConclusionFinished?.();
        } else {
          transitionToListening();
        }
      };

      utterance.onerror = () => {
        setInterviewerAudioLevel(0);
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

  // Background microphone listener during AI speaking for barge-in detection
  const startBargeInListener = async () => {
    try {
      let stream = candidateStreamRef.current;
      if (!stream || !stream.active) {
        stream = await enableCandidateCamera();
      }
      if (!stream) return;

      const audioTracks = stream.getAudioTracks();
      if (!audioTracks.length) return;

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!candidateAudioCtxRef.current || candidateAudioCtxRef.current.state === "closed") {
        candidateAudioCtxRef.current = new AudioCtx();
      }
      const audioCtx = candidateAudioCtxRef.current;
      if (audioCtx.state === "suspended") {
        await audioCtx.resume().catch(() => {});
      }

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      candidateAnalyserRef.current = analyser;

      // Audio-only stream to prevent touching video tracks
      const audioOnlyStream = new MediaStream(audioTracks);
      const source = audioCtx.createMediaStreamSource(audioOnlyStream);
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      let lastCheck = performance.now();

      const checkBargeIn = () => {
        if (!candidateAnalyserRef.current || currentAudioRef.current === null) return;

        candidateAnalyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const avg = sum / bufferLength;
        const currentLevel = Math.min(100, Math.round((avg / 128) * 100));

        setCandidateAudioLevel(currentLevel);
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
      let stream = candidateStreamRef.current;
      if (!stream || !stream.active) {
        stream = await enableCandidateCamera();
      }
      if (!stream) {
        throw new Error("No media stream available.");
      }

      // Ensure candidate video element is attached to live camera
      if (candidateVideoRef.current && candidateVideoRef.current.srcObject !== stream) {
        candidateVideoRef.current.srcObject = stream;
        candidateVideoRef.current.play().catch(() => {});
      }

      const audioTracks = stream.getAudioTracks();
      if (!audioTracks.length) {
        throw new Error("No audio tracks available on media stream.");
      }

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!candidateAudioCtxRef.current || candidateAudioCtxRef.current.state === "closed") {
        candidateAudioCtxRef.current = new AudioCtx();
      }
      const audioCtx = candidateAudioCtxRef.current;
      if (audioCtx.state === "suspended") {
        await audioCtx.resume().catch(() => {});
      }

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      candidateAnalyserRef.current = analyser;

      // Audio-only stream to record speech without affecting video tracks
      const audioOnlyStream = new MediaStream(audioTracks);
      const source = audioCtx.createMediaStreamSource(audioOnlyStream);
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
      const recorder = new MediaRecorder(audioOnlyStream, options);
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
        if (!candidateAnalyserRef.current || mediaRecorderRef.current?.state !== "recording") return;

        candidateAnalyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const avg = sum / bufferLength;
        const currentLevel = Math.min(100, Math.round((avg / 128) * 100));

        setCandidateAudioLevel(currentLevel);
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
      // Keep camera active and do not set hasPermission to false
      setVoiceState("error");
      setErrorMessage("Microphone audio stream could not be started. Click Retry Speaking to try again.");
    }
  };

  // Candidate finishes speaking - stops audio recorder only without affecting camera video track
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
      setProcessingPhase("transcribing");
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

      // Only a genuinely empty transcript is rejected here. The three-character
      // floor that used to stand in this place threw away real answers: "No",
      // "10" and "AC" are complete spoken responses to questions that invite
      // them. The server already rejects silence and hallucination loops with a
      // 400 handled above, so anything reaching here is speech it stood behind.
      if (!transcript) {
        setVoiceState("error");
        setErrorMessage("I didn't catch that clearly. Please speak naturally into your microphone and try again.");
        return;
      }

      const audioUrl = URL.createObjectURL(audioBlob);

      const totalTurnMs = Math.round(performance.now() - turnStartTimeRef.current);
      setLatencyMetrics((m) => ({ ...m, totalMs: totalTurnMs }));

      // Submit transcript strictly to interview engine
      setProcessingPhase("evaluating");
      await onAnswerSubmitted(transcript, audioUrl);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to process speech";
      setVoiceState("error");
      setErrorMessage(errorMsg || "An error occurred while processing speech. Click below to retry speaking.");
    }
  };

  // Unblock autoplay and resume audio playback upon user interaction
  const handleUnblockAudio = async () => {
    try {
      if (ttsAudioCtxRef.current && ttsAudioCtxRef.current.state === "suspended") {
        await ttsAudioCtxRef.current.resume();
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

  // Replay question audio via Single Audio Owner without altering turn or state
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
                backgroundColor: "#0c111d",
                borderRadius: "18px",
                overflow: "hidden",
                border: `1px solid ${voiceState === "ai_speaking" ? "#4f46e5" : "#1e293b"}`,
                display: "flex",
                flexDirection: "column",
                boxShadow:
                  voiceState === "ai_speaking"
                    ? "0 10px 30px rgba(0,0,0,0.25), 0 0 0 3px rgba(79, 70, 229, 0.18)"
                    : "0 10px 30px rgba(0,0,0,0.25)",
                transition: "border-color 0.3s ease, box-shadow 0.3s ease"
              }}
            >
              {/* Female Interviewer Visual */}
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
                  src="/avatars/interviewer.jpg"
                  alt="AI Technical Interviewer"
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    objectPosition: "center 20%",
                    display: "block"
                  }}
                />

                {/* Speaking Energy Radial Glow */}
                {voiceState === "ai_speaking" && (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      boxShadow: "inset 0 0 60px rgba(99, 102, 241, 0.45)",
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
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    minWidth: 0,
                    flexShrink: 1,
                    overflow: "hidden"
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
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: "#ffffff", fontSize: "0.85rem", fontWeight: 700, lineHeight: 1.2, whiteSpace: "nowrap" }}>
                      AI Technical Interviewer
                    </div>
                    <div
                      style={{
                        color: "#94a3b8",
                        fontSize: "0.72rem",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}
                      title={`${companyName} Hiring Lead • ${roleTitle}`}
                    >
                      {companyName} Hiring Lead • {roleTitle}
                    </div>
                  </div>
                </div>

                {/* Dynamic State Badge */}
                <div style={{ flexShrink: 0, marginLeft: "0.5rem" }}>
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
                        whiteSpace: "nowrap",
                        boxShadow: "0 2px 8px rgba(99, 102, 241, 0.5)"
                      }}
                    >
                      <span aria-hidden="true" style={{ display: "inline-flex", alignItems: "center", gap: "2px", height: "12px" }}>
                        {[0, 1, 2, 3].map((i) => (
                          <span
                            key={i}
                            className="wave-bar"
                            style={{
                              width: "2.5px",
                              height: "12px",
                              borderRadius: "2px",
                              backgroundColor: "#ffffff",
                              animationDelay: `${i * 0.13}s`
                            }}
                          />
                        ))}
                      </span>
                      Interviewer speaking
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
                      <Zap size={14} /> Interrupted — listening
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
                        whiteSpace: "nowrap",
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
                      {voiceState === "candidate_speaking" ? "Recording your answer" : "Listening to your answer"}
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
                      <Loader2 size={14} className="animate-spin" />{" "}
                      {processingPhase === "transcribing"
                        ? "Transcribing your answer"
                        : "Analyzing your response"}
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
                      <AlertCircle size={14} /> Attention Needed
                    </span>
                  )}
                </div>
              </div>

              {/* Bottom Overlay: Spectrum Visualizer */}
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
                    {voiceState === "ai_speaking" ? "Kokoro Neural Speech Stream" : "Studio Audio Engine"}
                  </span>
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
                border: `1px solid ${
                  voiceState === "listening" || voiceState === "candidate_speaking" ? "#10b981" : "#1e293b"
                }`,
                display: "flex",
                flexDirection: "column",
                boxShadow:
                  voiceState === "listening" || voiceState === "candidate_speaking"
                    ? "0 10px 30px rgba(0,0,0,0.25), 0 0 0 3px rgba(16, 185, 129, 0.18)"
                    : "0 10px 30px rgba(0,0,0,0.25)",
                transition: "border-color 0.3s ease, box-shadow 0.3s ease"
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
                  display: cameraActive && hasPermission !== false ? "block" : "none"
                }}
              />

              {hasPermission === false && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: "#0f172a",
                    color: "#94a3b8",
                    padding: "2rem",
                    textAlign: "center"
                  }}
                >
                  <CameraOff size={44} color="#f43f5e" style={{ marginBottom: "0.75rem" }} />
                  <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", marginBottom: "0.35rem" }}>
                    Camera Access Needed
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8", maxWidth: "240px", lineHeight: 1.4 }}>
                    Please grant camera and microphone access to display your live video feed.
                  </span>
                  <button
                    onClick={enableCandidateCamera}
                    style={{
                      marginTop: "1rem",
                      padding: "0.45rem 1rem",
                      backgroundColor: "rgba(255,255,255,0.12)",
                      border: "1px solid rgba(255,255,255,0.2)",
                      borderRadius: "8px",
                      color: "#ffffff",
                      fontSize: "0.8rem",
                      cursor: "pointer"
                    }}
                  >
                    Allow Camera Access
                  </button>
                </div>
              )}

              {cameraActive === false && hasPermission !== false && (
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
                  <div
                    style={{
                      width: "60px",
                      height: "5px",
                      backgroundColor: "rgba(255,255,255,0.2)",
                      borderRadius: "3px",
                      overflow: "hidden"
                    }}
                  >
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

          {/* Conversational Interviewer Subtitle / Caption (Visible on Speech) */}
          {activeSubtitleText && (
            <div
              className="saas-card"
              style={{
                padding: "1.25rem 1.5rem",
                backgroundColor: "#ffffff",
                borderRadius: "16px",
                border: "1px solid #e2e8f0",
                boxShadow: "0 2px 8px rgba(0,0,0,0.04)"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                <div
                  style={{
                    fontSize: "0.78rem",
                    color: "#4f46e5",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    fontWeight: 700
                  }}
                >
                  Interviewer
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  {voiceState === "ai_speaking" && (
                    <span style={{ fontSize: "0.78rem", color: "#6366f1", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.3rem" }}>
                      <Volume2 size={14} className="spin" /> Speaking...
                    </span>
                  )}
                  {(voiceState === "listening" || voiceState === "candidate_speaking") && (
                    <span style={{ fontSize: "0.78rem", color: "#10b981", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.3rem" }}>
                      <Mic size={14} /> Listening...
                    </span>
                  )}
                </div>
              </div>

              <p
                style={{
                  fontSize: "1.12rem",
                  fontWeight: 500,
                  color: "#0f172a",
                  lineHeight: 1.6,
                  margin: 0
                }}
              >
                &ldquo;{activeSubtitleText}&rdquo;
              </p>

              {/* Action Bar with Voice & Video Lifecycle Controls */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                  marginTop: "1rem",
                  paddingTop: "0.85rem",
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
                    <Play size={16} /> Start Interview
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
                      onClick={handleListenAgain}
                      className="btn btn-secondary"
                      style={{ padding: "0.65rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                    >
                      <RotateCcw size={15} /> Listen Again
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
                      className="btn btn-secondary"
                      style={{ padding: "0.55rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                    >
                      Start Answer
                    </button>

                    <button
                      onClick={handleListenAgain}
                      className="btn btn-secondary"
                      style={{ padding: "0.55rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                    >
                      <RotateCcw size={15} /> Listen Again
                    </button>
                  </>
                )}

                {(voiceState === "error" || voiceState === "idle") && (
                  <>
                    <button
                      onClick={() => {
                        setErrorMessage(null);
                        transitionToListening();
                      }}
                      disabled={submitting}
                      className="btn btn-primary"
                      style={{ padding: "0.65rem 1.5rem", fontSize: "0.9rem", borderRadius: "10px" }}
                    >
                      <RefreshCw size={16} /> Retry Speaking
                    </button>

                    <button
                      onClick={handleListenAgain}
                      className="btn btn-secondary"
                      style={{ padding: "0.65rem 1.25rem", fontSize: "0.85rem", borderRadius: "10px" }}
                    >
                      <RotateCcw size={15} /> Listen Again
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

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

    </div>
  );
};
