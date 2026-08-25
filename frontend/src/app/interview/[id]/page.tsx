"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { InterviewTimer } from "@/components/InterviewTimer";
import { AudioRecorder } from "@/components/AudioRecorder";
import { VideoInteractionRoom } from "@/components/VideoInteractionRoom";
import { MonacoCodingRoom } from "@/components/MonacoCodingRoom";
import { apiRequest } from "@/lib/api";
import { InterviewSession, AnswerTurnResponse, Question } from "@/types";
import { Send, CheckCircle2, AlertCircle, Award, Sparkles, FileText, ChevronDown, ChevronUp } from "lucide-react";

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
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading Adaptive Interview Session #{interviewId}...</p>
      </div>
    );
  }

  const qText = currentQuestion?.question_text || "Please provide your detailed answer regarding this technical topic.";
  const currentTopic = session.state?.current_topic || "Core Technical";
  const stage = session.state?.interview_stage || "core";

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Authoritative Header */}
        <div className="glass-card" style={{ padding: "1.25rem 1.5rem", marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{session.company_name || "Company"} • {session.role_title || "Role"}</span>
            <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{session.interview_type || "Technical"} ({session.mode})</span>
            <span className="badge badge-success">Stage: {stage}</span>
            <span className="badge badge-warning">Topic: {currentTopic}</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <InterviewTimer initialRemainingSeconds={session.state?.time_remaining_seconds || 1800} onExpire={() => router.push(`/reports/${interviewId}`)} />
            <button onClick={handleFinishEarly} className="btn btn-secondary" style={{ padding: "0.4rem 0.8rem", fontSize: "0.8rem", color: "var(--accent-rose)" }}>
              Finish Session
            </button>
          </div>
        </div>

        {/* Video interaction room if mode === video */}
        {session.mode === "video" && (
          <VideoInteractionRoom currentQuestionText={qText} />
        )}

        {/* Active Question Box */}
        <div className="glass-card" style={{ padding: "2rem", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Question #{ (session.state?.questions_asked_count || 0) + 1 } • Difficulty: <strong style={{ color: "var(--accent-cyan)", textTransform: "capitalize" }}>{session.state?.difficulty || "medium"}</strong>
            </span>
            <span className="badge badge-primary" style={{ textTransform: "capitalize" }}>{currentQuestion?.question_type || "Technical"}</span>
          </div>

          <h2 style={{ fontSize: "1.35rem", marginTop: "0.75rem", lineHeight: 1.5 }}>
            {qText}
          </h2>

          {currentQuestion?.expected_concepts && currentQuestion.expected_concepts.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "1rem" }}>
              {currentQuestion.expected_concepts.map((c) => (
                <span key={c} className="badge badge-primary" style={{ fontSize: "0.75rem" }}>Key Focus: {c}</span>
              ))}
            </div>
          )}
        </div>

        {/* Realtime Last Turn Evaluation Feedback Display */}
        {lastTurnResponse && lastTurnResponse.evaluation && (
          <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem", background: "rgba(16, 185, 129, 0.08)", borderColor: "rgba(16, 185, 129, 0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#6ee7b7", marginBottom: "0.5rem" }}>
              <CheckCircle2 size={18} />
              <strong>Turn Evaluation: {lastTurnResponse.evaluation.overall_question_score} / 10</strong>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", lineHeight: 1.5 }}>
              {lastTurnResponse.evaluation.feedback_text}
            </p>
          </div>
        )}

        {/* Audio Recording Interface if mode === audio */}
        {session.mode === "audio" && (
          <div style={{ marginBottom: "1.5rem" }}>
            <AudioRecorder onTranscriptReceived={(t, url) => { setAnswerText(t); handleSubmitAnswer(t, url); }} />
          </div>
        )}

        {/* Answer Input Box */}
        <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
          <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
            Your Answer / Rationale:
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
              <Send size={18} /> {submitting ? "Evaluating..." : "Submit Answer Turn"}
            </button>
          </div>
        </div>

        {/* Past Answered Turns in Session */}
        {session.answers && session.answers.length > 0 && (
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <div
              onClick={() => setShowHistory(!showHistory)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
            >
              <h4 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <FileText size={18} color="var(--primary)" /> Answered Questions in this Session ({session.answers.length})
              </h4>
              {showHistory ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>

            {showHistory && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1.25rem" }}>
                {session.answers.map((a, idx) => (
                  <div key={a.id} style={{ background: "rgba(0,0,0,0.3)", padding: "1rem", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "var(--text-primary)", marginBottom: "0.3rem" }}>
                      Q{idx + 1}: {a.question_text}
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0.4rem 0" }}>
                      <strong>Your Answer:</strong> {a.candidate_answer_text}
                    </p>
                    {a.evaluation && (
                      <div style={{ fontSize: "0.8rem", color: "#6ee7b7", marginTop: "0.4rem" }}>
                        Score: {a.evaluation.overall_question_score}/10 • Feedback: {a.evaluation.feedback_text}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

