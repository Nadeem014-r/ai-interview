from fastapi import APIRouter, Depends, UploadFile, File, Response
from fastapi.responses import StreamingResponse
import io
from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService
from app.schemas.interview import VoiceSynthesizeRequest

router = APIRouter(prefix="/voice", tags=["Voice Speech-to-Text & Text-to-Speech"])

@router.post("/stt")
async def transcribe_speech(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    res = await SpeechToTextService.transcribe(audio_bytes, filename=file.filename or "recording.wav")
    return res

@router.post("/tts")
async def synthesize_text(req: VoiceSynthesizeRequest):
    audio_bytes = await TextToSpeechService.synthesize(req.text, voice_id=req.voice_id or "default")
    
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
        media_type = "audio/mpeg"

    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Accept-Ranges": "bytes",
        }
    )
