"use client";

import React, { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { InterviewSession, Question, AnswerItem } from "@/types";
import { InterviewTimer } from "@/components/InterviewTimer";
import { AudioRecorder } from "@/components/AudioRecorder";
import { VideoInteractionRoom } from "@/components/VideoInteractionRoom";
import { VoiceInterviewRoom } from "@/components/VoiceInterviewRoom";
import { Send, ChevronDown, ChevronUp, Bot, Sparkles, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

type InterviewLifecycle = "LOADING" | "PRE_START" | "ACTIVE" | "CONCLUDING" | "REPORT_GENERATING" | "COMPLETED";

export default function InterviewInteractionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id;

  const [lifecycle, setLifecycle] = useState<InterviewLifecycle>("LOADING");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answers, setAnswers] = useState<AnswerItem[]>([]);
  const [lastEvaluation, setLastEvaluation] = useState<{ overall_question_score: number; feedback_text: string } | null>(null);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showTurnHistory, setShowTurnHistory] = useState(false);
  const [concludingMessage, setConcludingMessage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState("");
  const [preStartSeconds, setPreStartSeconds] = useState(10);

  const lifecycleRef = useRef<InterviewLifecycle>("LOADING");
  const initializedRef = useRef(false);
  const finishingRef = useRef(false);
  const consecutiveBasicWrongAnswersRef = useRef<number>(0);

  const updateLifecycle = (next: InterviewLifecycle) => {
    lifecycleRef.current = next;
    setLifecycle(next);
  };

  useEffect(() => {
    if (requireAuth(router) && sessionId && !initializedRef.current) {
      initializedRef.current = true;
      loadSession();
    }
  }, [sessionId]);

  // Pre-start preparation countdown (10s for Text, 30s for Audio/Video)
  useEffect(() => {
    if (lifecycle !== "PRE_START") return;

    // Seamlessly unlock browser audio context on any interaction during preparation
    const unlockAudio = () => {
      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          ctx.resume().catch(() => {});
        }
      } catch (e) {}
    };

    window.addEventListener("click", unlockAudio, { once: true });
    window.addEventListener("touchstart", unlockAudio, { once: true });
    window.addEventListener("keydown", unlockAudio, { once: true });

    const interval = setInterval(() => {
      setPreStartSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          updateLifecycle("ACTIVE");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(interval);
      window.removeEventListener("click", unlockAudio);
      window.removeEventListener("touchstart", unlockAudio);
      window.removeEventListener("keydown", unlockAudio);
    };
  }, [lifecycle]);

  async function loadSession() {
    updateLifecycle("LOADING");
    setErrorMessage("");
    try {
      const sessData: InterviewSession = await apiRequest(`/interviews/${sessionId}`);
      setSession(sessData);

      if (sessData.answers && sessData.answers.length > 0) {
        setAnswers(sessData.answers);
        const latestAns = sessData.answers[sessData.answers.length - 1];
        if (latestAns?.evaluation) {
          setLastEvaluation({
            overall_question_score: latestAns.evaluation.overall_question_score || latestAns.evaluation.correctness_score || 0,
            feedback_text: latestAns.evaluation.feedback_text || ""
          });
        }
      }

      if (sessData.status === "completed") {
        updateLifecycle("COMPLETED");
        router.push(`/reports/${sessionId}`);
        return;
      }

      if (sessData.current_question) {
        setCurrentQuestion(sessData.current_question);
        if (sessData.current_question.question_text && (sessData.mode === "audio" || sessData.mode === "video")) {
          // Pre-warm and pre-synthesize Kokoro TTS audio in background during countdown
          const qText = sessData.current_question.question_text;
          const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
          const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
          fetch(`${baseUrl}/voice/tts`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ text: qText })
          }).then(async (res) => {
            if (res.ok) {
              const blob = await res.blob();
              if (blob && blob.size > 0 && typeof window !== "undefined") {
                const url = URL.createObjectURL(blob);
                (window as any).__TTS_AUDIO_CACHE__ = (window as any).__TTS_AUDIO_CACHE__ || {};
                (window as any).__TTS_AUDIO_CACHE__[qText] = url;
              }
            }
          }).catch((e) => console.warn("Background TTS pre-warm:", e));
        }
      }

      // Preparation countdown: 10s for text mode, 30s for audio / video mode
      if (!sessData.answers || sessData.answers.length === 0) {
        setPreStartSeconds(sessData.mode === "text" ? 10 : 30);
        updateLifecycle("PRE_START");
      } else {
        updateLifecycle("ACTIVE");
      }
    } catch (err: any) {
      console.error("Failed to load interview session:", err);
      setErrorMessage(err.message || "Failed to load interview session.");
      updateLifecycle("ACTIVE");
    }
  }

  const triggerConcludedFlow = (message: string) => {
    if (finishingRef.current || lifecycleRef.current === "CONCLUDING" || lifecycleRef.current === "COMPLETED") {
      return;
    }
    finishingRef.current = true;
    updateLifecycle("CONCLUDING");
    setConcludingMessage(message);

    // Keep polite conclusion message visible for approximately 5 seconds so candidate can read it comfortably
    setTimeout(() => {
      executeFinishAndNavigate();
    }, 5000);
  };

  const executeFinishAndNavigate = async () => {
    updateLifecycle("REPORT_GENERATING");
    try {
      await apiRequest(`/interviews/${sessionId}/finish`, {
        method: "POST"
      });
      updateLifecycle("COMPLETED");
      router.push(`/reports/${sessionId}`);
    } catch (err) {
      console.error("Finish interview error:", err);
      updateLifecycle("COMPLETED");
      router.push(`/reports/${sessionId}`);
    }
  };

  const handleTimerExpired = () => {
    if (lifecycleRef.current !== "ACTIVE") return;
    triggerConcludedFlow("Thank you for your time. Based on your responses, we'll conclude the interview here.");
  };

  const handleManualFinish = () => {
    if (lifecycleRef.current !== "ACTIVE") return;
    triggerConcludedFlow("Thank you for your time. Based on your responses, we'll conclude the interview here.");
  };

  const handleSubmitAnswer = async (spokenText?: string, audioUrl?: string) => {
    const textToSubmit = (spokenText || candidateAnswer).trim();
    if (!textToSubmit || !currentQuestion || submitting || lifecycleRef.current !== "ACTIVE") {
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    try {
      const response: any = await apiRequest(`/interviews/${sessionId}/answer`, {
        method: "POST",
        body: JSON.stringify({
          answer_text: textToSubmit,
          audio_url: audioUrl || null,
          stt_latency_ms: 0
        }),
      });

      if (lifecycleRef.current !== "ACTIVE") {
        return;
      }

      setCandidateAnswer("");

      // 1. Update evaluation feedback
      let score = 5.0;
      let feedback = "Answer recorded.";
      if (response.evaluation) {
        score = response.evaluation.overall_question_score ?? response.evaluation.correctness_score ?? 5.0;
        feedback = response.evaluation.feedback_text || "Answer recorded.";
        setLastEvaluation({
          overall_question_score: score,
          feedback_text: feedback
        });

        // 2. Add turn to answer history
        setAnswers((prev) => [
          ...prev,
          {
            id: Date.now(),
            question_id: currentQuestion.id,
            question_text: currentQuestion.question_text,
            candidate_answer_text: textToSubmit,
            created_at: new Date().toISOString(),
            evaluation: {
              overall_question_score: score,
              feedback_text: feedback,
              correctness_score: response.evaluation.correctness_score,
              relevance_score: response.evaluation.relevance_score,
              reasoning_score: response.evaluation.reasoning_score,
              depth_score: response.evaluation.depth_score,
              communication_score: response.evaluation.communication_score
            }
          }
        ]);
      }

      // 3. Evaluate 3 Consecutive Basic Wrong Answers rule
      const isBasicQuestion =
        currentQuestion.difficulty === "easy" ||
        currentQuestion.difficulty === "intro" ||
        currentQuestion.topic?.toLowerCase().includes("basic") ||
        session?.target_level === "junior";

      if (isBasicQuestion) {
        if (score < 4.0) {
          consecutiveBasicWrongAnswersRef.current += 1;
        } else {
          consecutiveBasicWrongAnswersRef.current = 0;
        }
      } else {
        if (score >= 4.0) {
          consecutiveBasicWrongAnswersRef.current = 0;
        }
      }

      // Check if 3 consecutive basic wrong answers threshold is reached
      if (consecutiveBasicWrongAnswersRef.current >= 3) {
        triggerConcludedFlow("Thank you for your time. Based on your responses, we'll conclude the interview here.");
        return;
      }

      // 4. Update state machine progression
      if (response.interview_state && session) {
        setSession((prev) => prev ? { ...prev, state: response.interview_state } : prev);
      }

      // 5. Handle completion or next question progression
      if (response.is_completed || !response.next_question) {
        triggerConcludedFlow(
          response.closing_message || "Thank you for your time. Based on your responses, we'll conclude the interview here."
        );
      } else {
        setCurrentQuestion(response.next_question);
      }
    } catch (err: any) {
      console.error("Answer submission error:", err);
      setErrorMessage(err.message || "Failed to submit answer.");
    } finally {
      setSubmitting(false);
    }
  };

  if (lifecycle === "LOADING") {
    return (
      <WorkspaceLayout sectionTitle="Interview Workspace">
        <div style={{ maxWidth: "880px", margin: "0 auto" }}>
          <div className="saas-card skeleton" style={{ height: "420px" }} />
        </div>
      </WorkspaceLayout>
    );
  }

  if (!session) {
    return (
      <WorkspaceLayout sectionTitle="Interview Workspace">
        <div style={{ maxWidth: "880px", margin: "0 auto" }}>
          <div className="saas-card" style={{ padding: "3rem", textAlign: "center" }}>
            <AlertCircle size={36} color="#e11d48" style={{ marginBottom: "0.5rem" }} />
            <h3 style={{ fontSize: "1.1rem", color: "#09090b" }}>Interview Session Not Found</h3>
            <p style={{ color: "#71717a", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
              {errorMessage || "Unable to find the requested interview session."}
            </p>
            <button onClick={() => router.push("/interview/configure")} className="btn btn-primary">
              Configure New Interview
            </button>
          </div>
        </div>
      </WorkspaceLayout>
    );
  }

  // Actual interview duration derived directly from configured duration (e.g. 10m = 600s, 15m = 900s, 30m = 1800s)
  const configuredDurationSeconds = session.duration_minutes
    ? session.duration_minutes * 60
    : 900;

  const remainingSeconds = session.state?.time_remaining_seconds && session.state.time_remaining_seconds > 0
    ? session.state.time_remaining_seconds
    : configuredDurationSeconds;

  const currentQuestionNumber = answers.length + 1;
  const isConcludingOrGenerating = lifecycle === "CONCLUDING" || lifecycle === "REPORT_GENERATING";

  return (
    <WorkspaceLayout
      sectionTitle={`Interview Session #${session.id}`}
      sectionSubtitle={`${session.role_title || `Role #${session.role_id}`} • ${session.interview_type || "Technical"} (${session.mode})`}
    >
      <div style={{ maxWidth: "880px", margin: "0 auto" }}>
        {/* Telemetry Status Bar with Prominent Countdown Timer across all modes */}
        <div
          className="saas-card"
          style={{
            padding: "0.85rem 1.25rem",
            marginBottom: "1.25rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "0.75rem"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="badge badge-neutral" style={{ textTransform: "capitalize" }}>
              {session.interview_type || "Technical"} Focus
            </span>
            <span className="badge badge-neutral" style={{ textTransform: "uppercase" }}>
              {session.mode} Mode
            </span>
            <span className="badge badge-warning" style={{ textTransform: "capitalize" }}>
              Difficulty: {currentQuestion?.difficulty || session.state?.difficulty || "medium"}
            </span>
            {lifecycle === "ACTIVE" && (
              <span className="badge badge-neutral">
                Question {currentQuestionNumber}
              </span>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
            <InterviewTimer
              initialRemainingSeconds={remainingSeconds}
              isActive={lifecycle === "ACTIVE"}
              onExpire={handleTimerExpired}
            />
            {lifecycle === "ACTIVE" && (
              <button
                onClick={handleManualFinish}
                className="btn btn-secondary"
                style={{ fontSize: "0.78rem", padding: "0.3rem 0.65rem" }}
              >
                Finish Interview
              </button>
            )}
          </div>
        </div>

        {errorMessage && (
          <div
            style={{
              padding: "0.65rem 1rem",
              backgroundColor: "var(--accent-rose-light)",
              border: "1px solid #fecdd3",
              borderRadius: "8px",
              color: "var(--accent-rose)",
              fontSize: "0.85rem",
              marginBottom: "1.25rem",
              display: "flex",
              alignItems: "center",
              gap: "0.45rem"
            }}
          >
            <AlertCircle size={15} /> {errorMessage}
          </div>
        )}

        {/* 10-SECOND PRE-START PREPARATION SCREEN: Displayed exclusively before the first question starts */}
        {lifecycle === "PRE_START" && (
          <div
            className="saas-card"
            style={{
              padding: "4rem 2rem",
              textAlign: "center",
              backgroundColor: "#ffffff",
              border: "1px solid #e4e4e7",
              boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "360px",
              gap: "1rem"
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "50%",
                backgroundColor: "#f4f4f5",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#09090b"
              }}
            >
              <Bot size={24} />
            </div>

            <div>
              <span
                style={{
                  fontSize: "0.85rem",
                  textTransform: "uppercase",
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                  color: "#71717a",
                  display: "block",
                  marginBottom: "0.75rem"
                }}
              >
                INTERVIEW STARTING
              </span>

              <div
                style={{
                  fontSize: "4.5rem",
                  fontWeight: 800,
                  color: "#09090b",
                  fontFamily: "monospace",
                  lineHeight: 1,
                  margin: "0.5rem 0"
                }}
              >
                {preStartSeconds}
              </div>

              <p
                style={{
                  fontSize: "0.95rem",
                  color: "#71717a",
                  fontWeight: 500,
                  margin: "0.75rem 0 0"
                }}
              >
                {session.mode === "text"
                  ? "Your interview will begin automatically in 10 seconds. Get ready."
                  : "Your interview will begin automatically in 30 seconds. Please prepare yourself."}
              </p>
            </div>
          </div>
        )}

        {/* DEDICATED CONCLUSION SCREEN: Rendered exclusively when CONCLUDING or REPORT_GENERATING */}
        {isConcludingOrGenerating ? (
          <div
            className="saas-card"
            style={{
              padding: "3rem 2rem",
              textAlign: "center",
              backgroundColor: "#ffffff",
              border: "1px solid #e4e4e7",
              boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "1rem"
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "50%",
                backgroundColor: "var(--accent-brand-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent-brand)"
              }}
            >
              <Sparkles size={24} />
            </div>

            <div>
              <h3 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#09090b", margin: "0 0 0.5rem" }}>
                Interview Concluded
              </h3>
              <p
                style={{
                  fontSize: "1rem",
                  color: "#3730a3",
                  maxWidth: "600px",
                  margin: "0 auto",
                  lineHeight: 1.5,
                  fontWeight: 500
                }}
              >
                {concludingMessage || "Thank you for your time. Based on your responses, we'll conclude the interview here."}
              </p>
            </div>

            <div
              style={{
                marginTop: "1.25rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 1rem",
                backgroundColor: "#f4f4f5",
                borderRadius: "8px",
                fontSize: "0.85rem",
                color: "#52525b",
                fontWeight: 500
              }}
            >
              <Loader2 size={15} className="spin" />
              <span>
                {lifecycle === "REPORT_GENERATING"
                  ? "Generating your performance intelligence report..."
                  : "Finalizing interview assessment..."}
              </span>
            </div>
          </div>
        ) : lifecycle === "ACTIVE" ? (
          /* ACTIVE INTERVIEW ROOM: Rendered exclusively when ACTIVE */
          <>
            {/* Video Mode Room */}
            {session.mode === "video" && (
              <div style={{ marginBottom: "1.25rem" }}>
                <VideoInteractionRoom
                  interviewId={Number(sessionId)}
                  currentQuestionText={currentQuestion?.question_text || "Listening for question..."}
                  questionNumber={currentQuestionNumber}
                  difficulty={currentQuestion?.difficulty || session.state?.difficulty || "medium"}
                  questionType={currentQuestion?.question_type || session.interview_type || "technical"}
                  expectedConcepts={currentQuestion?.expected_concepts || []}
                  lastEvaluation={lastEvaluation}
                  onAnswerSubmitted={async (spoken, audioUrl) => {
                    setCandidateAnswer(spoken);
                    await handleSubmitAnswer(spoken, audioUrl);
                  }}
                  submitting={submitting}
                  companyName={session.company_name}
                  roleTitle={session.role_title}
                />
              </div>
            )}

            {/* Audio Mode Room */}
            {session.mode === "audio" && (
              <div style={{ marginBottom: "1.25rem" }}>
                <VoiceInterviewRoom
                  interviewId={Number(sessionId)}
                  currentQuestionText={currentQuestion?.question_text || "Listening for question..."}
                  questionNumber={currentQuestionNumber}
                  difficulty={currentQuestion?.difficulty || session.state?.difficulty || "medium"}
                  questionType={currentQuestion?.question_type || session.interview_type || "technical"}
                  expectedConcepts={currentQuestion?.expected_concepts || []}
                  lastEvaluation={lastEvaluation}
                  onAnswerSubmitted={async (spoken, audioUrl) => {
                    setCandidateAnswer(spoken);
                    await handleSubmitAnswer(spoken, audioUrl);
                  }}
                  submitting={submitting}
                />
              </div>
            )}

            {/* Text Mode Active Question Card with In-Card Timer Header */}
            {session.mode === "text" && currentQuestion && (
              <div className="saas-card" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                    <div style={{ backgroundColor: "#09090b", padding: "0.35rem", borderRadius: "6px", color: "#ffffff" }}>
                      <Bot size={15} />
                    </div>
                    <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "#09090b" }}>
                      Interviewer Question #{currentQuestionNumber} ({currentQuestion.topic || "Technical"})
                    </span>
                  </div>

                  {/* In-Card High Visibility Timer for Text Mode */}
                  <InterviewTimer
                    initialRemainingSeconds={remainingSeconds}
                    isActive={lifecycle === "ACTIVE"}
                    onExpire={handleTimerExpired}
                  />
                </div>

                <p style={{ fontSize: "1.1rem", fontWeight: 500, color: "#09090b", lineHeight: 1.5, margin: "0 0 1rem" }}>
                  {currentQuestion.question_text}
                </p>

                {currentQuestion.expected_concepts && currentQuestion.expected_concepts.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", alignItems: "center" }}>
                    <span style={{ fontSize: "0.7rem", color: "#71717a", fontWeight: 600, textTransform: "uppercase" }}>Focus:</span>
                    {currentQuestion.expected_concepts.map((fa: string) => (
                      <span key={fa} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>{fa}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Turn Evaluation Feedback Callout */}
            {lastEvaluation && (
              <div style={{ padding: "0.85rem 1rem", backgroundColor: "var(--accent-emerald-light)", border: "1px solid #a7f3d0", borderRadius: "10px", marginBottom: "1.25rem" }}>
                <span style={{ fontSize: "0.72rem", color: "#059669", textTransform: "uppercase", fontWeight: 700, display: "block", marginBottom: "0.2rem" }}>
                  Previous Answer Score: {lastEvaluation.overall_question_score} / 10
                </span>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#065f46", lineHeight: 1.4 }}>
                  {lastEvaluation.feedback_text}
                </p>
              </div>
            )}

            {/* Text Mode Response Area */}
            {session.mode === "text" && currentQuestion && (
              <div className="saas-card" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <label style={{ fontSize: "0.825rem", fontWeight: 600, color: "#52525b" }}>Your Response</label>
                  <AudioRecorder
                    onTranscriptReceived={(transcript) => {
                      setCandidateAnswer(transcript);
                    }}
                  />
                </div>

                <textarea
                  rows={5}
                  value={candidateAnswer}
                  onChange={(e) => setCandidateAnswer(e.target.value)}
                  className="form-input"
                  placeholder="Type your structured answer here, addressing technical design, tradeoffs, and relevant examples..."
                  style={{ marginBottom: "1rem" }}
                />

                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => handleSubmitAnswer()}
                    disabled={submitting || !candidateAnswer.trim()}
                    className="btn btn-primary"
                    style={{ padding: "0.6rem 1.25rem", fontSize: "0.85rem" }}
                  >
                    <Send size={14} /> <span>{submitting ? "Evaluating response..." : "Submit Answer"}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Turn History Drawer */}
            {answers.length > 0 && (
              <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
                <div
                  onClick={() => setShowTurnHistory(!showTurnHistory)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                >
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#09090b", margin: 0 }}>
                    Question & Response History ({answers.length})
                  </h3>
                  {showTurnHistory ? <ChevronUp size={16} color="#71717a" /> : <ChevronDown size={16} color="#71717a" />}
                </div>

                {showTurnHistory && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "1rem" }}>
                    {answers.map((a, idx) => (
                      <div key={a.id || idx} style={{ padding: "0.85rem", backgroundColor: "#fafafa", borderRadius: "8px", border: "1px solid #f4f4f5", fontSize: "0.825rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                          <strong style={{ color: "#09090b" }}>Q{idx + 1}: {a.question_text}</strong>
                          {a.evaluation?.overall_question_score !== undefined && (
                            <span className="badge badge-success">{a.evaluation.overall_question_score} / 10</span>
                          )}
                        </div>
                        <p style={{ margin: "0.35rem 0", color: "#52525b" }}>
                          <span style={{ fontWeight: 600, color: "#71717a" }}>Answer:</span> {a.candidate_answer_text}
                        </p>
                        {a.evaluation?.feedback_text && (
                          <p style={{ margin: 0, color: "#059669", fontSize: "0.78rem" }}>
                            <span style={{ fontWeight: 600 }}>Feedback:</span> {a.evaluation.feedback_text}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        ) : null}
      </div>
    </WorkspaceLayout>
  );
}
