"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { InterviewTimer } from "@/components/InterviewTimer";
import { AudioRecorder } from "@/components/AudioRecorder";
import { VideoInteractionRoom } from "@/components/VideoInteractionRoom";
import { VoiceInterviewRoom } from "@/components/VoiceInterviewRoom";
import { apiRequest } from "@/lib/api";
import { requireAuth } from "@/lib/auth";
import { InterviewSession, AnswerTurnResponse, Question } from "@/types";
import { Send, CheckCircle2, FileText, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

export default function InterviewRoomPage() {
  const params = useParams();
  const router = useRouter();
  const interviewId = params.id;

  const [session, setSession] = useState<InterviewSession | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [lastTurnResponse, setLastTurnResponse] = useState<AnswerTurnResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (!requireAuth(router)) return;
    async function loadInterviewSession() {
      try {
        const data: InterviewSession = await apiRequest(`/interviews/${interviewId}`);
        setSession(data);
        if (data.current_question) {
          setCurrentQuestion(data.current_question);
        }
        if (data.status === "completed") {
          router.push(`/reports/${interviewId}`);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    if (interviewId) loadInterviewSession();
  }, [interviewId]);

  const handleSubmitAnswer = async (overrideText?: string, audioUrl?: string) => {
    const textToSend = overrideText || answerText;
    if (!textToSend.trim()) return;
    setSubmitting(true);

    try {
      const res: AnswerTurnResponse = await apiRequest(`/interviews/${interviewId}/answer`, {
        method: "POST",
        body: JSON.stringify({
          answer_text: textToSend,
          audio_url: audioUrl || null
        })
      });
      setLastTurnResponse(res);
      setAnswerText("");

      // Update session state locally
      if (session && res.interview_state) {
        setSession({
          ...session,
          state: res.interview_state
        });
      }

      if (res.is_completed) {
        router.push(`/reports/${interviewId}`);
      } else if (res.next_question) {
        setCurrentQuestion(res.next_question);
      }
    } catch (err: any) {
      alert(err.message || "Error submitting answer turn.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinishEarly = async () => {
    if (confirm("Are you sure you want to finish the interview session now? Final report will be generated.")) {
      try {
        await apiRequest(`/interviews/${interviewId}/finish`, { method: "POST" });
        router.push(`/reports/${interviewId}`);
      } catch (err) {
        alert("Failed to terminate interview.");
      }
    }
  };

  if (loading || !session) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "#64748b" }}>Loading Adaptive Interview Session #{interviewId}...</p>
      </div>
    );
  }

  const qText = currentQuestion?.question_text || "Please provide your detailed answer regarding this technical topic.";
  const currentTopic = session.state?.current_topic || "Core Technical";
  const stage = session.state?.interview_stage || "core";
  const isVoiceMode = session.mode === "voice" || session.mode === "audio";

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      <Navbar />

      <main style={{ maxWidth: "1000px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Authoritative Header */}
        <div className="saas-card" style={{ padding: "1rem 1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0", marginBottom: "1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{session.company_name || "Company"} • {session.role_title || "Role"}</span>
            <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{session.interview_type || "Technical"} ({session.mode})</span>
            <span className="badge badge-success">Stage: {stage}</span>
            <span className="badge badge-warning">Topic: {currentTopic}</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <InterviewTimer initialRemainingSeconds={session.state?.time_remaining_seconds || 1800} onExpire={() => router.push(`/reports/${interviewId}`)} />
            <button onClick={handleFinishEarly} className="btn btn-outline-danger" style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}>
              Finish Session
            </button>
          </div>
        </div>

        {/* VIDEO MODE (Production-Grade Realtime Video Interview Room) */}
        {session.mode === "video" ? (
          <VideoInteractionRoom
            interviewId={Number(interviewId)}
            currentQuestionText={qText}
            questionNumber={(session.state?.questions_asked_count || 0) + 1}
            difficulty={session.state?.difficulty || "medium"}
            questionType={currentQuestion?.question_type || "Technical"}
            expectedConcepts={currentQuestion?.expected_concepts || []}
            lastEvaluation={lastTurnResponse?.evaluation}
            onAnswerSubmitted={async (transcript, audioUrl) => {
              await handleSubmitAnswer(transcript, audioUrl);
            }}
            submitting={submitting}
            companyName={session.company_name}
            roleTitle={session.role_title}
          />
        ) : isVoiceMode ? (
          /* VOICE-TO-VOICE MODE (Pure Voice Interaction Room) */
          <VoiceInterviewRoom
            interviewId={Number(interviewId)}
            currentQuestionText={qText}
            questionNumber={(session.state?.questions_asked_count || 0) + 1}
            difficulty={session.state?.difficulty || "medium"}
            questionType={currentQuestion?.question_type || "Technical"}
            expectedConcepts={currentQuestion?.expected_concepts || []}
            lastEvaluation={lastTurnResponse?.evaluation}
            onAnswerSubmitted={async (transcript, audioUrl) => {
              await handleSubmitAnswer(transcript, audioUrl);
            }}
            submitting={submitting}
          />
        ) : (
          /* TEXT MODE */
          <>
            {/* Active Question Box */}
            <div className="saas-card" style={{ padding: "2rem", backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #e2e8f0", marginBottom: "1.25rem", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.8rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
                  Question #{ (session.state?.questions_asked_count || 0) + 1 } • Difficulty: <strong style={{ color: "#4f46e5", textTransform: "capitalize" }}>{session.state?.difficulty || "medium"}</strong>
                </span>
                <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{currentQuestion?.question_type || "Technical"}</span>
              </div>

              <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#0f172a", marginTop: "0.75rem", lineHeight: 1.5 }}>
                {qText}
              </h2>

              {currentQuestion?.expected_concepts && currentQuestion.expected_concepts.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "1rem" }}>
                  {currentQuestion.expected_concepts.map((c) => (
                    <span key={c} className="badge badge-primary" style={{ fontSize: "0.75rem" }}>Focus: {c}</span>
                  ))}
                </div>
              )}
            </div>

            {/* Realtime Last Turn Evaluation Feedback Display */}
            {lastTurnResponse && lastTurnResponse.evaluation && (
              <div className="saas-card" style={{ padding: "1.25rem", marginBottom: "1.25rem", backgroundColor: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#047857", marginBottom: "0.35rem" }}>
                  <CheckCircle2 size={18} />
                  <strong style={{ fontSize: "0.95rem" }}>Turn Evaluation: {lastTurnResponse.evaluation.overall_question_score} / 10</strong>
                </div>
                <p style={{ color: "#334155", fontSize: "0.88rem", lineHeight: 1.5 }}>
                  {lastTurnResponse.evaluation.feedback_text}
                </p>
              </div>
            )}

            {/* Text Mode Answer Input Box */}
            <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #e2e8f0", marginBottom: "1.25rem", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#334155", marginBottom: "0.5rem" }}>
                Your Answer / Technical Rationale:
              </label>
              <textarea
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                rows={5}
                className="form-input"
                placeholder="Type your technical answer here in detail..."
                style={{ marginBottom: "1rem" }}
              />

              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button onClick={() => handleSubmitAnswer()} disabled={submitting || !answerText.trim()} className="btn btn-primary" style={{ padding: "0.75rem 1.5rem" }}>
                  <Send size={16} /> {submitting ? "Evaluating..." : "Submit Answer Turn"}
                </button>
              </div>
            </div>
          </>
        )}

        {/* Past Answered Turns in Session */}
        {session.answers && session.answers.length > 0 && (
          <div className="saas-card" style={{ padding: "1.5rem", backgroundColor: "#ffffff", borderRadius: "14px", border: "1px solid #e2e8f0" }}>
            <div
              onClick={() => setShowHistory(!showHistory)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
            >
              <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: "0.45rem" }}>
                <FileText size={18} color="#4f46e5" /> Answered Questions in this Session ({session.answers.length})
              </h3>
              {showHistory ? <ChevronUp size={18} color="#64748b" /> : <ChevronDown size={18} color="#64748b" />}
            </div>

            {showHistory && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "1rem" }}>
                {session.answers.map((a, idx) => (
                  <div key={a.id} style={{ backgroundColor: "#f8fafc", padding: "1rem", borderRadius: "10px", border: "1px solid #f1f5f9" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a", marginBottom: "0.25rem" }}>
                      Q{idx + 1}: {a.question_text}
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "#475569", margin: "0.35rem 0" }}>
                      <strong>Your Answer:</strong> {a.candidate_answer_text}
                    </p>
                    {a.evaluation && (
                      <div style={{ fontSize: "0.8rem", color: "#047857", marginTop: "0.35rem", fontWeight: 600 }}>
                        Score: {a.evaluation.overall_question_score}/10 • Feedback: {a.evaluation.feedback_text}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
