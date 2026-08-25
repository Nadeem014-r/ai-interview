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
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")
