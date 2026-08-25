"""Phase 10B: Realtime Event Constants.

Defines all supported client-to-server and server-to-client event types.
"""

from typing import Set


class RealtimeEvents:
    """Standardized event string constants for realtime WebSocket communication."""

    # Connection & Session Handshake (Client -> Server)
    CONNECTION_INIT = "connection.init"
    SESSION_RESUME = "session.resume"
    HEARTBEAT_PING = "heartbeat.ping"
    SESSION_CLOSE = "session.close"

    # Audio Streaming (Client -> Server)
    AUDIO_START = "audio.start"
    AUDIO_CHUNK = "audio.chunk"
    AUDIO_END = "audio.end"

    # Interview Control (Client -> Server)
    INTERVIEW_PAUSE = "interview.pause"
    INTERVIEW_RESUME = "interview.resume"

    # Handshake & Lifecycle Responses (Server -> Client)
    CONNECTION_ACCEPTED = "connection.accepted"
    CONNECTION_ERROR = "connection.error"
    HEARTBEAT_PONG = "heartbeat.pong"
    SESSION_STARTED = "session.started"
    SESSION_RESUMED = "session.resumed"
    SESSION_CLOSED = "session.closed"

    # Transcription Events (Server -> Client)
    TRANSCRIPT_PARTIAL = "transcript.partial"
    TRANSCRIPT_FINAL = "transcript.final"

    # Interview Engine Events (Server -> Client)
    INTERVIEW_QUESTION = "interview.question"
    INTERVIEW_EVALUATION = "interview.evaluation"
    INTERVIEW_STATE = "interview.state"

    # TTS Synthesis Events (Server -> Client)
    TTS_START = "tts.start"
    TTS_CHUNK = "tts.chunk"
    TTS_END = "tts.end"

    # General Feedback (Server -> Client)
    WARNING = "warning"
    ERROR = "error"

    @classmethod
    def client_events(cls) -> Set[str]:
        """Set of events that a client is permitted to send."""
        return {
            cls.CONNECTION_INIT,
            cls.SESSION_RESUME,
            cls.HEARTBEAT_PING,
            cls.AUDIO_START,
            cls.AUDIO_CHUNK,
            cls.AUDIO_END,
            cls.INTERVIEW_PAUSE,
            cls.INTERVIEW_RESUME,
            cls.SESSION_CLOSE,
        }

    @classmethod
    def server_events(cls) -> Set[str]:
        """Set of events that the server emits."""
        return {
            cls.CONNECTION_ACCEPTED,
            cls.CONNECTION_ERROR,
            cls.HEARTBEAT_PONG,
            cls.SESSION_STARTED,
            cls.SESSION_RESUMED,
            cls.SESSION_CLOSED,
            cls.TRANSCRIPT_PARTIAL,
            cls.TRANSCRIPT_FINAL,
            cls.INTERVIEW_QUESTION,
            cls.INTERVIEW_EVALUATION,
            cls.INTERVIEW_STATE,
            cls.TTS_START,
            cls.TTS_CHUNK,
            cls.TTS_END,
            cls.WARNING,
            cls.ERROR,
        }
