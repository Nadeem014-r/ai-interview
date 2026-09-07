import logging
from fastapi import APIRouter, Depends, UploadFile, File, Response, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.core.security import get_current_user_payload
from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService
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
        audio_bytes = await TextToSpeechService.synthesize(req.text, voice_id=req.voice_id or "default")
    except Exception as e:
        # Simulated audio may stand in only where mocks are permitted. In
        # production it would return a 440 Hz tone as the interviewer's voice
        # under HTTP 200, hiding the outage from the caller.
        from app.ai.factory import _implicit_mock_allowed

        if not _implicit_mock_allowed():
            logger.error(f"TextToSpeechService error: {e}")
            raise HTTPException(status_code=503, detail="Speech synthesis is currently unavailable.")
        logger.warning(f"TextToSpeechService error: {e}. Attempting fallback synthesis.")
        try:
            from app.ai.mock_provider import MockTTSProvider
            audio_bytes = await MockTTSProvider().synthesize_speech(req.text, voice_id=req.voice_id or "default")
        except Exception as fb_err:
            logger.error(f"TTS fallback also failed: {fb_err}")
            raise HTTPException(status_code=500, detail="TTS synthesis failed.")
    
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

