import logging
from fastapi import APIRouter, Depends, UploadFile, File, Response, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.core.security import get_current_user_payload
from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService
from app.providers.config import INTERVIEWER_VOICE_ID
from app.schemas.interview import VoiceSynthesizeRequest

logger = logging.getLogger("ai_interviewer.voice_api")

router = APIRouter(prefix="/voice", tags=["Voice Speech-to-Text & Text-to-Speech"])

@router.post("/stt")
async def transcribe_speech(
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user_payload),
):
    audio_bytes = await file.read()
    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")
    try:
        res = await SpeechToTextService.transcribe(audio_bytes, filename=file.filename or "recording.wav")
        # Sizes and durations only -- never the transcript, which is candidate speech.
        logger.info(
            "stt_timing bytes=%d validation_ms=%s stt_ms=%s total_ms=%s",
            len(audio_bytes),
            res.get("validation_latency_ms"),
            res.get("stt_latency_ms"),
            res.get("latency_ms"),
        )
        return res
    except Exception as e:
        # Check if it was empty / silent audio or invalid format
        from app.voice.exceptions import (
            AudioValidationError,
            NoSpeechDetectedError,
            UnsupportedAudioFormatError,
        )
        if isinstance(e, (AudioValidationError, UnsupportedAudioFormatError)):
            logger.warning(f"Rejected audio upload: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        if isinstance(e, NoSpeechDetectedError):
            # The server and the provider both worked; the recording simply held
            # no speech. Reporting 500 told the candidate the system had broken
            # and raised a false alarm in error monitoring, so this is a 400 with
            # an instruction the candidate can act on.
            logger.info("No speech detected in uploaded audio.")
            raise HTTPException(
                status_code=400,
                detail="No speech was detected in the recording. Please speak clearly and try again.",
            )
        logger.error(f"Speech transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech transcription error: {str(e)}")

@router.post("/tts")
async def synthesize_text(
    req: VoiceSynthesizeRequest,
    payload: dict = Depends(get_current_user_payload),
):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty for TTS synthesis.")

    try:
        audio_bytes = await TextToSpeechService.synthesize(
            req.text, voice_id=req.voice_id or INTERVIEWER_VOICE_ID
        )
    except Exception as e:
        # No simulated audio here, in any environment. This endpoint speaks as
        # the interviewer, and the mock's 440 Hz tone returned under HTTP 200
        # was indistinguishable from success to the caller: the browser cached
        # it, played it, and the candidate heard a beep -- or, when the caller
        # treated it as a failure, heard a different voice for that one line.
        # Reporting the outage lets the client retry the same voice instead.
        logger.error(f"TextToSpeechService error: {e}")
        raise HTTPException(status_code=503, detail="Speech synthesis is currently unavailable.")


    # Detect audio format from magic bytes
    if audio_bytes.startswith(b"ID3") or (len(audio_bytes) > 1 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0):
        media_type = "audio/mpeg"
    elif audio_bytes.startswith(b"RIFF") and len(audio_bytes) >= 12 and audio_bytes[8:12] == b"WAVE":
        media_type = "audio/wav"
    elif audio_bytes.startswith(b"OggS"):
        media_type = "audio/ogg"
    elif audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        media_type = "audio/webm"
    else:
        media_type = "audio/wav"

    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Accept-Ranges": "bytes",
        }
    )

