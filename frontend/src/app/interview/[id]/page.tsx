"use client";

import React, { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { armInterviewAudio, fetchInterviewerAudio } from "@/lib/tts";
import { InterviewSession, Question, AnswerItem } from "@/types";
import { InterviewTimer } from "@/components/InterviewTimer";
import { VideoInteractionRoom } from "@/components/VideoInteractionRoom";
import { VoiceInterviewRoom } from "@/components/VoiceInterviewRoom";
import { InterviewCountdown } from "@/components/InterviewCountdown";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";
import { Send, ChevronDown, ChevronUp, Bot, Sparkles, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

// PRE_START is the preparation countdown and READY is the state it lands in
// once the countdown has actually run out. They are separate because the
// single Begin control only exists in READY: while PRE_START is on screen
// there is nothing to press, so the preparation window cannot be skipped.
type InterviewLifecycle = "LOADING" | "PRE_START" | "READY" | "ACTIVE" | "CONCLUDING" | "REPORT_GENERATING" | "COMPLETED";

// Standard preparation window before the first question, identical for text,
// voice and video so every mode gets the same run-up.
const PRE_START_SECONDS = 30;

// Labels for the stages the adaptive engine actually reports. Anything it sends
// that is not listed here is shown as-is rather than guessed at.
const STAGE_LABELS: Record<string, string> = {
  intro: "Warm-up",
  core: "Core questions",
  deep_dive: "Deep dive",
  adaptive_probe: "Follow-up probe",
  recovery: "Recalibrating",
  wrapup: "Wrapping up",
  early_conclusion: "Concluding"
};

export default function InterviewInteractionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id;

  const [lifecycle, setLifecycle] = useState<InterviewLifecycle>("LOADING");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answers, setAnswers] = useState<AnswerItem[]>([]);
  // Deliberately no per-turn evaluation state. A candidate who is shown a score
  // and a critique after every answer stops having a conversation and starts
  // managing a grade -- and no real interviewer marks you aloud between
  // questions. Evaluations are still computed and stored on every turn, because
  // the adaptive engine steers on them; they are released to the candidate in
  // the final report, once the session is over.
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showTurnHistory, setShowTurnHistory] = useState(false);
  const [concludingMessage, setConcludingMessage] = useState<string>("");
  // Spoken reaction to the answer just given, voiced ahead of the next question.
  const [interviewerAck, setInterviewerAck] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [preStartSeconds, setPreStartSeconds] = useState(PRE_START_SECONDS);
  const [reportId, setReportId] = useState<number | null>(null);
  const [reportReady, setReportReady] = useState(false);

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

  // Pre-start preparation countdown (30s across text, audio and video).
  //
  // The countdown no longer starts the interview by itself. Browsers refuse
  // programmatic audio until the document has been interacted with, and a timer
  // is not an interaction: on a freshly opened tab the first question's audio
  // was rejected and that one line was spoken by the browser's own voice
  // instead of the interviewer's. The candidate now presses Begin, which is a
  // real gesture, and arming the audio inside it covers every line after it.
  useEffect(() => {
    if (lifecycle !== "PRE_START") return;

    const interval = setInterval(() => {
      setPreStartSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [lifecycle]);

  // Countdown exhausted: move to READY, which is the only state that offers a
  // Begin control. Nothing starts here -- the candidate still has to press it.
  useEffect(() => {
    if (lifecycle === "PRE_START" && preStartSeconds === 0) {
      updateLifecycle("READY");
    }
  }, [lifecycle, preStartSeconds]);

  // Begin the interview from a genuine click, so interviewer audio is armed
  // before the first question is spoken.
  const handleBeginInterview = async () => {
    // Only reachable from READY, so a stray call during the countdown -- or a
    // second click on the same button -- cannot cut the preparation short.
    if (lifecycleRef.current !== "READY") return;
    // Text mode is silent: there is no interviewer audio to arm.
    const ok = session?.mode === "text" ? true : await armInterviewAudio();
    if (!ok) {
      // The room shows its own "enable audio" control if playback is still
      // blocked; starting is still correct, the candidate is not stuck.
      console.warn("Interview audio could not be armed on Begin.");
    }
    updateLifecycle("ACTIVE");
  };

  async function loadSession() {
    updateLifecycle("LOADING");
    setErrorMessage("");
    try {
      const sessData: InterviewSession = await apiRequest(`/interviews/${sessionId}`);
      setSession(sessData);

      if (sessData.answers && sessData.answers.length > 0) {
        setAnswers(sessData.answers);
      }

      if (sessData.status === "completed") {
        updateLifecycle("COMPLETED");
        router.push(`/reports/${sessionId}`);
        return;
      }

      if (sessData.current_question) {
        setCurrentQuestion(sessData.current_question);
        if (sessData.current_question.question_text && (sessData.mode === "audio" || sessData.mode === "video")) {
          // Pre-synthesise question one during the countdown, through the same
          // shared cache the room reads. It used to write to a cache of its own
          // while the room kept another, so a pre-synthesis that had not
          // finished by the time the room mounted was simply repeated -- two
          // synthesis jobs for one line on the same CPU. One in-flight map now
          // means the room awaits this request instead of starting a second.
          void fetchInterviewerAudio(sessData.current_question.question_text);
        }
      }

      // Preparation countdown: uniform 30s for every interview mode
      if (!sessData.answers || sessData.answers.length === 0) {
        setPreStartSeconds(PRE_START_SECONDS);
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

  // Finalise once, then stop waiting. The report is built on the server after
  // the response returns, so the candidate is not held on a spinner for work
  // they do not need to watch, and closing the tab does not cancel it.
  const executeFinishAndNavigate = async () => {
    updateLifecycle("REPORT_GENERATING");
    try {
      const res: any = await apiRequest(`/interviews/${sessionId}/finish`, {
        method: "POST"
      });
      if (res?.report_id) {
        setReportId(res.report_id);
        setReportReady(true);
      }
    } catch (err) {
      // The status poll below recovers from this: finishing is idempotent, and
      // the interview is already marked complete server-side once it succeeds.
      console.error("Finish interview error:", err);
    }
  };

  // Poll for the report at a deliberately unhurried interval. The answer comes
  // from the stored report row, so it survives a refresh, a new tab or a
  // different device -- and a candidate who leaves now can open the report
  // later from their history.
  useEffect(() => {
    if (lifecycle !== "REPORT_GENERATING" || reportReady) return;

    let cancelled = false;
    const check = async () => {
      try {
        const res: any = await apiRequest(`/interviews/${sessionId}/report-status`);
        if (cancelled) return;
        if (res?.status === "ready") {
          setReportId(res.report_id ?? null);
          setReportReady(true);
        }
      } catch (err) {
        console.warn("Report status check failed; will retry.", err);
      }
    };

    check();
    const timer = setInterval(check, 8000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [lifecycle, reportReady, sessionId]);

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
          // Name the question this answer was written for, so a resubmission
          // (retry after a timeout, a second tab) is recognised as the same
          // turn instead of being scored against the next question.
          question_id: currentQuestion.id,
          audio_url: audioUrl || null,
          stt_latency_ms: 0
        }),
      });

      if (lifecycleRef.current !== "ACTIVE") {
        return;
      }

      setCandidateAnswer("");
      setInterviewerAck(
        typeof response.interviewer_ack === "string" && response.interviewer_ack.trim()
          ? response.interviewer_ack.trim()
          : null
      );

      // 1. The turn score drives the local early-conclusion rule below. It is
      //    read and never stored in state, so it cannot reach the screen.
      const score: number =
        response.evaluation?.overall_question_score ??
        response.evaluation?.correctness_score ??
        5.0;

      // 2. Add the turn to the history the candidate can look back at: the
      //    question and what they said, with no assessment attached.
      setAnswers((prev) => [
        ...prev,
        {
          id: Date.now(),
          question_id: currentQuestion.id,
          question_text: currentQuestion.question_text,
          candidate_answer_text: textToSubmit,
          created_at: new Date().toISOString()
        }
      ]);

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
            <AlertCircle size={36} color="var(--accent-rose)" style={{ marginBottom: "0.5rem" }} />
            <h3 style={{ fontSize: "1.1rem", color: "var(--text-primary)" }}>Interview Session Not Found</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
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
  const isCodingTurn = currentQuestion?.question_type === "coding";
  // A coding solution is submitted exactly once. Once an answer exists for this
  // question the workspace locks: a refresh, a back button or a second click
  // finds the turn already on record rather than sending it again.
  const codingSubmitted =
    !!currentQuestion && answers.some((a) => a.question_id === currentQuestion.id);

  // The interview is adaptive: no total question count is guaranteed by the
  // backend, so progress is expressed as questions completed so far plus the
  // stage the engine reports. Never a fixed "X of N".
  const rawStage = session.state?.interview_stage;
  const stageLabel = rawStage
    ? STAGE_LABELS[rawStage] || rawStage.replace(/_/g, " ")
    : null;
  const activeTopic = currentQuestion?.topic || session.state?.current_topic || null;

  return (
    <WorkspaceLayout
      sectionTitle={`Interview Session #${session.id}`}
      sectionSubtitle={`${session.role_title || `Role #${session.role_id}`} • ${session.interview_type || "Technical"} (${session.mode})`}
      // A session that has started -- including a coding turn, which is part of
      // the interview and not the standalone practice tool -- holds the
      // sidebar. Navigating away mid-interview loses the turn in progress.
      lockNavigation={lifecycle === "PRE_START" || lifecycle === "READY" || lifecycle === "ACTIVE"}
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
            gap: "0.75rem",
            rowGap: "0.5rem"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="badge badge-neutral" style={{ textTransform: "capitalize" }}>
              {session.interview_type || "Technical"} Focus
            </span>
            <span className="badge badge-neutral" style={{ textTransform: "uppercase" }}>
              {session.mode} Mode
            </span>
            {/* Before the interview starts this shows the session's configured
                difficulty, never question one's -- nothing about the first
                question is on screen until the candidate presses Begin. */}
            <span className="badge badge-warning" style={{ textTransform: "capitalize" }}>
              Difficulty:{" "}
              {lifecycle === "ACTIVE"
                ? currentQuestion?.difficulty || session.state?.difficulty || "medium"
                : session.state?.difficulty || "medium"}
            </span>
            {lifecycle === "ACTIVE" && stageLabel && (
              <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>
                Stage: {stageLabel}
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

          {/* Adaptive progress: completed turns are known, the total is not. */}
          {lifecycle === "ACTIVE" && (
            <div
              style={{
                width: "100%",
                borderTop: "1px solid var(--border-subtle)",
                paddingTop: "0.7rem",
                marginTop: "0.15rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "0.6rem"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-primary)" }}>
                  Question {currentQuestionNumber}
                </span>
                {activeTopic && (
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>· {activeTopic}</span>
                )}
              </div>

              {/* One segment per completed turn, plus the live one. The trailing
                  fade signals that more questions may follow without promising
                  a count the engine has not decided yet. */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  flexWrap: "wrap",
                  justifyContent: "flex-end",
                  rowGap: "4px",
                  maxWidth: "100%"
                }}
                role="img"
                aria-label={`${answers.length} question${answers.length === 1 ? "" : "s"} completed, currently on question ${currentQuestionNumber}. The interview is adaptive, so the total is not fixed.`}
              >
                {answers.length > 12 ? (
                  <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--accent-brand)", marginRight: "0.2rem" }}>
                    {answers.length} answered
                  </span>
                ) : (
                  answers.map((a, idx) => (
                    <span
                      key={a.id || idx}
                      style={{
                        width: "16px",
                        height: "5px",
                        borderRadius: "9999px",
                        backgroundColor: "#6d5cff",
                        opacity: 0.55,
                        transition: "opacity 0.25s ease"
                      }}
                    />
                  ))
                )}
                <span
                  style={{
                    width: "30px",
                    height: "5px",
                    borderRadius: "9999px",
                    backgroundColor: "#6d5cff",
                    boxShadow: "0 0 0 3px rgba(79, 70, 229, 0.12)"
                  }}
                />
                <span
                  aria-hidden="true"
                  style={{
                    width: "22px",
                    height: "5px",
                    borderRadius: "9999px",
                    background: "linear-gradient(90deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 100%)"
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {errorMessage && (
          <div
            style={{
              padding: "0.65rem 1rem",
              backgroundColor: "var(--accent-rose-light)",
              border: "1px solid rgba(251, 113, 133, 0.32)",
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

        {/* PREPARATION SCREEN: uniform 30s run-up before the first question.
            There is deliberately no control here -- the preparation window is
            the same length for every candidate, so it cannot be skipped. */}
        {lifecycle === "PRE_START" && (
          <InterviewCountdown
            seconds={preStartSeconds}
            totalSeconds={PRE_START_SECONDS}
            mode={session.mode}
            roleTitle={session.role_title}
            companyName={session.company_name}
          />
        )}

        {/* READY SCREEN: the countdown has finished and the interview waits on
            the candidate. This is the one and only start action, and the
            interview starts on this click rather than on the timer, because the
            click is what lets the browser play the interviewer's voice for the
            first question. The question itself stays hidden until then. */}
        {lifecycle === "READY" && (
          <>
            <InterviewCountdown
              seconds={0}
              totalSeconds={PRE_START_SECONDS}
              mode={session.mode}
              roleTitle={session.role_title}
              companyName={session.company_name}
              ready
            />
            <div style={{ textAlign: "center", marginTop: "1rem", marginBottom: "1.25rem" }}>
              <button
                onClick={handleBeginInterview}
                className="btn btn-primary"
                style={{ padding: "0.7rem 1.75rem", fontSize: "0.9rem" }}
              >
                Begin Interview
              </button>
              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.6rem" }}>
                Your interviewer will ask the first question as soon as you begin.
              </p>
            </div>
          </>
        )}

        {/* DEDICATED CONCLUSION SCREEN: Rendered exclusively when CONCLUDING or REPORT_GENERATING */}
        {isConcludingOrGenerating ? (
          <div
            className="saas-card"
            style={{
              padding: "3rem 2rem",
              textAlign: "center",
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
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
              <h3 style={{ fontSize: "1.35rem", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 0.5rem" }}>
                Interview Concluded
              </h3>
              <p
                style={{
                  fontSize: "1rem",
                  color: "var(--accent-brand-hover)",
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
                backgroundColor: reportReady ? "var(--accent-emerald-light)" : "var(--bg-subtle)",
                borderRadius: "8px",
                fontSize: "0.85rem",
                color: reportReady ? "var(--accent-emerald)" : "var(--text-secondary)",
                fontWeight: 500
              }}
              role="status"
              aria-live="polite"
            >
              {reportReady ? <CheckCircle2 size={15} /> : <Loader2 size={15} className="spin" />}
              <span>
                {lifecycle === "CONCLUDING"
                  ? "Finalizing interview assessment..."
                  : reportReady
                  ? "Your detailed report is ready."
                  : "Your interview is complete. Your detailed report is being prepared."}
              </span>
            </div>

            {lifecycle === "REPORT_GENERATING" && (
              <>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: "520px", margin: 0, lineHeight: 1.5 }}>
                  {reportReady
                    ? "You can open it now, or find it any time under your interview history."
                    : "Usually ready within a few minutes. You can safely close this page \u2014 your report will be waiting under your interview history."}
                </p>

                <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", justifyContent: "center" }}>
                  <button
                    onClick={() => router.push(`/reports/${sessionId}`)}
                    disabled={!reportReady}
                    className="btn btn-primary"
                    style={{ padding: "0.6rem 1.25rem", fontSize: "0.85rem" }}
                  >
                    View Report
                  </button>
                  <button
                    onClick={() => router.push("/history")}
                    className="btn btn-secondary"
                    style={{ padding: "0.6rem 1.25rem", fontSize: "0.85rem" }}
                  >
                    Back to Interview History
                  </button>
                </div>
              </>
            )}
          </div>
        ) : lifecycle === "ACTIVE" ? (
          /* ACTIVE INTERVIEW ROOM: Rendered exclusively when ACTIVE */
          <>
            {/* Coding turns take over the room in every mode: a compilable
                solution cannot be dictated, so the voice and video interviewers
                stand down for this one question and resume afterwards. The
                submission still goes through the same answer endpoint as every
                other turn, so idempotency and adaptive progression are unchanged. */}
            {isCodingTurn && currentQuestion && (
              <MonacoCodingRoom
                questionText={currentQuestion.question_text}
                expectedConcepts={currentQuestion.expected_concepts || []}
                onCodeSubmit={async (submission) => {
                  await handleSubmitAnswer(submission);
                }}
                submitting={submitting}
                submitted={codingSubmitted}
              />
            )}

            {/* Video Mode Room */}
            {!isCodingTurn && session.mode === "video" && (
              <div style={{ marginBottom: "1.25rem" }}>
                <VideoInteractionRoom
                  interviewId={Number(sessionId)}
                  currentQuestionText={currentQuestion?.question_text || "Listening for question..."}
                  questionNumber={currentQuestionNumber}
                  difficulty={currentQuestion?.difficulty || session.state?.difficulty || "medium"}
                  questionType={currentQuestion?.question_type || session.interview_type || "technical"}
                  expectedConcepts={currentQuestion?.expected_concepts || []}
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
            {!isCodingTurn && session.mode === "audio" && (
              <div style={{ marginBottom: "1.25rem" }}>
                <VoiceInterviewRoom
                  interviewId={Number(sessionId)}
                  currentQuestionText={currentQuestion?.question_text || "Listening for question..."}
                  currentQuestionId={currentQuestion?.id}
                  interviewerAck={interviewerAck}
                  questionNumber={currentQuestionNumber}
                  difficulty={currentQuestion?.difficulty || session.state?.difficulty || "medium"}
                  questionType={currentQuestion?.question_type || session.interview_type || "technical"}
                  expectedConcepts={currentQuestion?.expected_concepts || []}
                  onAnswerSubmitted={async (spoken, audioUrl) => {
                    setCandidateAnswer(spoken);
                    await handleSubmitAnswer(spoken, audioUrl);
                  }}
                  submitting={submitting}
                />
              </div>
            )}

            {/* Text Mode Live State Banner — names the current UI state so the
                candidate always knows whose turn it is. */}
            {!isCodingTurn && session.mode === "text" && currentQuestion && (
              <div
                role="status"
                aria-live="polite"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  padding: "0.6rem 1rem",
                  marginBottom: "0.85rem",
                  borderRadius: "10px",
                  border: `1px solid ${submitting ? "rgba(251, 191, 36, 0.32)" : "rgba(139, 125, 255, 0.28)"}`,
                  backgroundColor: submitting ? "var(--accent-amber-light)" : "var(--accent-brand-light)",
                  transition: "background-color 0.3s ease, border-color 0.3s ease"
                }}
              >
                <span
                  className={submitting ? undefined : "state-glow"}
                  style={{
                    width: "9px",
                    height: "9px",
                    borderRadius: "50%",
                    flexShrink: 0,
                    backgroundColor: submitting ? "var(--accent-amber)" : "var(--accent-brand)",
                    ["--state-glow-color" as any]: "rgba(79, 70, 229, 0.4)"
                  }}
                />
                <span style={{ fontSize: "0.82rem", fontWeight: 600, color: submitting ? "#92400e" : "#3730a3" }}>
                  {submitting ? "Analyzing your response" : "Your turn — write your answer"}
                </span>
                {submitting && (
                  <span
                    className="indeterminate-track"
                    aria-hidden="true"
                    style={{
                      flex: 1,
                      maxWidth: "160px",
                      height: "4px",
                      borderRadius: "9999px",
                      color: "var(--accent-amber)",
                      marginLeft: "auto"
                    }}
                  />
                )}
              </div>
            )}

            {/* Text Mode Active Question Card with In-Card Timer Header */}
            {!isCodingTurn && session.mode === "text" && currentQuestion && (
              <div
                className="saas-card"
                style={{
                  padding: "1.5rem",
                  marginBottom: "1.25rem",
                  borderColor: submitting ? "var(--border-subtle)" : "rgba(139, 125, 255, 0.4)",
                  opacity: submitting ? 0.72 : 1,
                  transition: "opacity 0.3s ease, border-color 0.3s ease"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                    <div style={{ backgroundColor: "#6d5cff", padding: "0.35rem", borderRadius: "6px", color: "#ffffff" }}>
                      <Bot size={15} />
                    </div>
                    <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--text-primary)" }}>
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

                <p style={{ fontSize: "1.1rem", fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.5, margin: "0 0 1rem" }}>
                  {currentQuestion.question_text}
                </p>

                {currentQuestion.expected_concepts && currentQuestion.expected_concepts.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", alignItems: "center" }}>
                    <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>Focus:</span>
                    {currentQuestion.expected_concepts.map((fa: string) => (
                      <span key={fa} className="badge badge-neutral" style={{ fontSize: "0.72rem" }}>{fa}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Text Mode Response Area */}
            {!isCodingTurn && session.mode === "text" && currentQuestion && (
              <div className="saas-card" style={{ padding: "1.5rem", marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <label style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--text-secondary)" }}>Your Response</label>
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
                    {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}{" "}
                    <span>{submitting ? "Analyzing your response..." : "Submit Answer"}</span>
                  </button>
                </div>

                {/* Lightweight placeholder for the question still being chosen. */}
                {submitting && (
                  <div style={{ marginTop: "1.1rem", paddingTop: "1rem", borderTop: "1px solid var(--border-subtle)" }}>
                    <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontWeight: 600, marginBottom: "0.55rem" }}>
                      Preparing the next question
                    </div>
                    <div className="skeleton" style={{ height: "12px", width: "82%", marginBottom: "0.45rem" }} />
                    <div className="skeleton" style={{ height: "12px", width: "58%" }} />
                  </div>
                )}
              </div>
            )}

            {/* Turn History Drawer */}
            {answers.length > 0 && (
              <div className="saas-card" style={{ padding: "1.25rem 1.5rem" }}>
                <div
                  onClick={() => setShowTurnHistory(!showTurnHistory)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                >
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
                    Question & Response History ({answers.length})
                  </h3>
                  {showTurnHistory ? <ChevronUp size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
                </div>

                {showTurnHistory && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "1rem" }}>
                    {answers.map((a, idx) => (
                      <div key={a.id || idx} style={{ padding: "0.85rem", backgroundColor: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-subtle)", fontSize: "0.825rem" }}>
                        <div style={{ marginBottom: "0.35rem" }}>
                          <strong style={{ color: "var(--text-primary)" }}>Q{idx + 1}: {a.question_text}</strong>
                        </div>
                        <p style={{ margin: "0.35rem 0 0", color: "var(--text-secondary)" }}>
                          <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Answer:</span> {a.candidate_answer_text}
                        </p>
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
