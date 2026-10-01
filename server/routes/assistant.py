# server/routes/assistant.py
"""Chat over meetings and spoken audio (text-to-speech)"""
import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.tts import TTSError, text_to_speech
from app.chatbot import answer_question
from app.export import minutes_to_speech_script
from crews.base_crew import describe_failure
from database import mongodb
from server.auth import CurrentUser, user_id
from server.routes.meetings import load_meeting

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assistant"])

# Cap on meetings loaded for "all meetings" questions (their minutes go into the prompt)
MAX_MEETINGS_IN_SCOPE = 20


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: List[ChatTurn] = []
    meeting_id: Optional[str] = None
    model: Optional[str] = None


@router.post("/chat")
def chat(body: ChatRequest, user: CurrentUser):
    if body.meeting_id:
        in_scope = [load_meeting(body.meeting_id, user)]
    else:
        owner = user_id(user)
        in_scope = [mongodb.get_meeting(m["id"], owner) for m in mongodb.list_meetings(owner)[:MAX_MEETINGS_IN_SCOPE]]
        in_scope = [m for m in in_scope if m]
    if not in_scope:
        raise HTTPException(status_code=400, detail="There are no meetings to ask about yet.")
    try:
        result = answer_question(body.question, [t.model_dump() for t in body.history], in_scope,
                                 meeting_id=body.meeting_id, model=body.model or None)
    except Exception as e:  # LLM failures (rate limits, overload) become a readable 503
        logger.exception("Chat failed")
        raise HTTPException(status_code=503, detail=describe_failure(e, failed="Could not answer"))
    sources = [{key: source.get(key) for key in ("title", "text", "start_ms", "meeting_id")} for source in result["sources"]]
    return {"answer": result["answer"], "sources": sources}


def _wav(text, voice):
    try:
        audio = text_to_speech(text, voice=voice)
    except TTSError as e:
        raise HTTPException(status_code=503, detail=f"Could not generate audio: {e}")
    return Response(content=audio, media_type="audio/wav")


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = "Kore"


@router.post("/tts")
def speak(body: SpeechRequest):
    return _wav(body.text, body.voice)


def _script(meeting, language):
    try:
        return minutes_to_speech_script(meeting, language or None)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))


@router.get("/meetings/{meeting_id}/speech-script")
def speech_script(meeting_id: str, user: CurrentUser, language: Optional[str] = None):
    return {"script": _script(load_meeting(meeting_id, user), language)}


class MeetingSpeechRequest(BaseModel):
    language: Optional[str] = None
    voice: str = "Kore"


@router.post("/meetings/{meeting_id}/speech")
def meeting_speech(meeting_id: str, body: MeetingSpeechRequest, user: CurrentUser):
    return _wav(_script(load_meeting(meeting_id, user), body.language), body.voice)
