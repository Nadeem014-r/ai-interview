import logging
from fastapi import APIRouter, Depends, UploadFile, File, Response, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService
from app.schemas.interview import VoiceSynthesizeRequest

logger = logging.getLogger("ai_interviewer.voice_api")

router = APIRouter(prefix="/voice", tags=["Voice Speech-to-Text & Text-to-Speech"])

@router.post("/stt")
async def transcribe_speech(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")
    try:
        res = await SpeechToTextService.transcribe(audio_bytes, filename=file.filename or "recording.wav")
        return res
    except Exception as e:
        logger.error(f"Speech transcription failed: {e}", exc_info=True)
        # Check if it was empty / silent audio or invalid format
        from app.voice.exceptions import AudioValidationError, UnsupportedAudioFormatError
        if isinstance(e, (AudioValidationError, UnsupportedAudioFormatError)):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Speech transcription error: {str(e)}")

@router.post("/tts")
async def synthesize_text(req: VoiceSynthesizeRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty for TTS synthesis.")

    try:
        audio_bytes = await TextToSpeechService.synthesize(req.text, voice_id=req.voice_id or "default")
    except Exception as e:
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

