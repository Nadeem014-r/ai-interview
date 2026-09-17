import { getStoredToken } from "./auth";

/**
 * Interviewer speech for the whole of a session.
 *
 * Every line an interviewer speaks has to come from the same person, and
 * before this module it did not: the page pre-synthesised question one into
 * one cache while each room kept its own, so the same text could be
 * synthesised twice, and any line whose synthesis failed was quietly handed to
 * the browser's Web Speech API -- a different voice, usually a male one on
 * Windows, for that line only. Both the cache and the voice therefore belong
 * to the session rather than to a component.
 */

// Named explicitly on every request. The server has a default, but sending the
// choice means the voice is a property of the session that is visible in the
// request rather than something each caller re-derives.
export const INTERVIEWER_VOICE_ID = "en_us_female_senior";

// Cache and in-flight map are module-level so the countdown's pre-synthesis and
// the room that later speaks the same line share one request. Two components
// asking for the same text get the same promise, and the second one does not
// start a second synthesis of it on the server's CPU.
const audioUrlCache: Record<string, string> = {};
const inFlight: Record<string, Promise<string | null>> = {};

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

/** A cached object URL for this line, if one has already been synthesised. */
export const getCachedInterviewerAudio = (text: string): string | null =>
  audioUrlCache[text] || null;

/**
 * Synthesise one line in the interviewer's voice.
 *
 * Returns null only when the server could not produce audio. Callers must not
 * substitute another voice for null -- retry, or continue without audio.
 */
export const fetchInterviewerAudio = async (text: string): Promise<string | null> => {
  if (!text || !text.trim()) return null;
  if (audioUrlCache[text]) return audioUrlCache[text];
  if (inFlight[text]) return inFlight[text];

  const promise = (async () => {
    try {
      const token = getStoredToken();
      const res = await fetch(`${apiBase()}/voice/tts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ text, voice_id: INTERVIEWER_VOICE_ID })
      });
      if (!res.ok) return null;
      const blob = await res.blob();
      if (!blob || blob.size === 0) return null;
      const url = URL.createObjectURL(blob);
      audioUrlCache[text] = url;
      return url;
    } catch {
      return null;
    } finally {
      delete inFlight[text];
    }
  })();

  inFlight[text] = promise;
  return promise;
};

/**
 * Synthesise a line, retrying a transient server failure once.
 *
 * The retry exists so that a single failed synthesis does not become a reason
 * to speak in a different voice. A 503 from the TTS endpoint is usually the
 * engine still warming; asking again a moment later gets the same voice, where
 * falling through to the browser synthesiser would not.
 */
export const fetchInterviewerAudioWithRetry = async (
  text: string,
  attempts = 2,
  delayMs = 1200
): Promise<string | null> => {
  for (let i = 0; i < attempts; i++) {
    const url = await fetchInterviewerAudio(text);
    if (url) return url;
    if (i < attempts - 1) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  return null;
};

// ── Audio arming ───────────────────────────────────────────────────────────
//
// Browsers refuse programmatic playback until the document has been interacted
// with. The interview used to move from its countdown into the first question
// on a timer alone, so on a freshly opened tab the first `audio.play()` was
// rejected and that one line fell back to the browser's own voice -- which is
// precisely the "question one sounds like someone else" symptom. Playing a
// silent buffer inside a real click grants the permission up front, for every
// line that follows.

let armed = false;

export const isAudioArmed = (): boolean => armed;

/** Call from inside a genuine user gesture (a click/tap handler). */
export const armInterviewAudio = async (): Promise<boolean> => {
  if (armed) return true;
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioCtx) {
      const ctx = new AudioCtx();
      if (ctx.state === "suspended") await ctx.resume();
    }
  } catch {
    // A blocked AudioContext does not stop <audio> playback; keep going.
  }

  try {
    // 0.05s of silence: enough for the gesture to count, short enough to be
    // inaudible and to finish before the countdown screen is replaced.
    const sampleRate = 8000;
    const frames = Math.floor(sampleRate * 0.05);
    const bytes = frames * 2;
    const buf = new ArrayBuffer(44 + bytes);
    const view = new DataView(buf);
    const ascii = (off: number, s: string) => {
      for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
    };
    ascii(0, "RIFF");
    view.setUint32(4, 36 + bytes, true);
    ascii(8, "WAVEfmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    ascii(36, "data");
    view.setUint32(40, bytes, true);

    const url = URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
    const probe = new Audio(url);
    probe.volume = 0;
    await probe.play();
    probe.pause();
    URL.revokeObjectURL(url);
    armed = true;
    return true;
  } catch {
    // Playback is still blocked. Report it so the caller can ask again rather
    // than starting the interview into silence.
    return false;
  }
};
