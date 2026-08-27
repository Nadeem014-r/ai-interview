from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.api.v1.auth import get_current_user_payload
from app.video.avatar import avatar_service

router = APIRouter(prefix="/video", tags=["video"])

class AvatarSessionStartRequest(BaseModel):
    interview_id: int
    avatar_id: Optional[str] = "senior_hiring_manager_1"
    voice_id: Optional[str] = "en_us_male_senior"

class AvatarIceCandidateRequest(BaseModel):
    session_id: str
    candidate: Dict[str, Any]

class AvatarSpeakRequest(BaseModel):
    session_id: str
    text: str = Field(..., min_length=1)

class AvatarSessionStopRequest(BaseModel):
    session_id: str

@router.post("/avatar/session/start", status_code=status.HTTP_201_CREATED)
async def start_avatar_session(
    req: AvatarSessionStartRequest,
    payload: dict = Depends(get_current_user_payload)
):
    """
    Creates an interactive AI Avatar streaming session.
    Returns WebRTC SDP offer, ICE servers, and session identification.
    """
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token.")

    session_data = avatar_service.create_session(
        user_id=user_id,
        interview_id=req.interview_id,
        avatar_id=req.avatar_id,
        voice_id=req.voice_id
    )
    return session_data

@router.post("/avatar/session/ice")
async def exchange_ice_candidate(
    req: AvatarIceCandidateRequest,
    payload: dict = Depends(get_current_user_payload)
):
    """
    Exchanges WebRTC ICE candidate with the streaming avatar server.
    """
    try:
        res = avatar_service.handle_ice_candidate(req.session_id, req.candidate)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/avatar/session/speak")
async def avatar_speak(
    req: AvatarSpeakRequest,
    payload: dict = Depends(get_current_user_payload)
):
    """
    Dispatches interviewer text to the avatar for synchronized lip-synced speech.
    """
    try:
        res = avatar_service.speak(req.session_id, req.text)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/avatar/session/stop")
async def stop_avatar_session(
    req: AvatarSessionStopRequest,
    payload: dict = Depends(get_current_user_payload)
):
    """
    Gracefully stops and closes the avatar WebRTC stream.
    """
    res = avatar_service.close_session(req.session_id)
    return res
