# server/routes/meetings.py
"""Meetings: generate (as a background job), list, view, edit, export, email and delete"""
import logging
import os
import re
import shutil
import tempfile
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from api import assemblyai
from api.email_service import active_provider, parse_recipients, send_minutes_email
from app.export import minutes_to_docx, minutes_to_html, minutes_to_markdown
from app.pipeline import InputError, generate_meeting
from crews import LANGUAGES
from database import mongodb, qdrant
from models import MeetingMinutes
from server.auth import CurrentUser, user_id
from server.jobs import jobs
from utils.transcript import parse_transcript_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meetings"])

EXPORTS = {
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", minutes_to_docx),
    "md": ("text/markdown; charset=utf-8", minutes_to_markdown),
    "html": ("text/html; charset=utf-8", minutes_to_html),
}


def load_meeting(meeting_id, user):
    """The user's meeting, or 404 (also for other users' meetings, so their ids reveal nothing)"""
    meeting = mongodb.get_meeting(meeting_id, user_id(user))
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


def file_slug(meeting):
    title = re.sub(r"[^A-Za-z0-9]+", "-", meeting.get("title", "meeting")).strip("-")[:60] or "meeting"
    return f"{title}-{meeting.get('meeting_date') or 'undated'}"


@router.get("/meetings")
def list_meetings(user: CurrentUser):
    return mongodb.list_meetings(user_id(user))


@router.post("/meetings", status_code=202)
def create_meeting(
    user: CurrentUser,
    title: str = Form(...),
    meeting_date: date = Form(...),
    source: str = Form(...),
    url: str = Form(""),
    text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    speakers_expected: int = Form(0),
    detect_language: bool = Form(True),
    redact_pii: bool = Form(False),
    fact_check: bool = Form(False),
    research: bool = Form(False),
    languages: str = Form(""),
    model: str = Form(""),
):
    """Validate the input, then generate the minutes in the background. Returns the job to poll."""
    if not title.strip():
        raise HTTPException(status_code=400, detail="Enter a meeting title.")
    source_args, cleanup_path = {}, None

    if source in ("recording", "url") and not assemblyai.is_configured():
        raise HTTPException(status_code=400, detail="Transcribing recordings needs ASSEMBLYAI_API_KEY. "
                                                    "You can upload or paste a transcript instead.")
    if source == "recording":
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="Upload a recording.")
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
        source_args = {"file_path": tmp.name, "filename": file.filename}
        cleanup_path = tmp.name
    elif source == "url":
        if not url.strip().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Enter a public http(s) link to the recording.")
        source_args = {"url": url.strip()}
    elif source == "transcript_file":
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="Upload a transcript file.")
        data = file.file.read()
        if not parse_transcript_file(file.filename, data)["text"].strip():
            raise HTTPException(status_code=400, detail="The transcript file is empty.")
        source_args = {"filename": file.filename, "data": data}
    elif source == "text":
        if not text.strip():
            raise HTTPException(status_code=400, detail="Paste the transcript text.")
        source_args = {"text": text}
    else:
        raise HTTPException(status_code=400, detail="Unknown source.")

    options = {
        "speakers_expected": speakers_expected or None, "detect_language": detect_language, "redact_pii": redact_pii,
        "fact_check": fact_check, "research": research,
        "languages": [lang for lang in (part.strip() for part in languages.split(",")) if lang in LANGUAGES],
    }

    def run(job):
        meeting_id = generate_meeting(title.strip(), meeting_date, source, owner_id=user_id(user), options=options,
                                      model=model or None, progress=job.report, cleanup_path=cleanup_path, **source_args)
        return {"meeting_id": meeting_id}

    job = jobs.start("generate", user_id(user), run)
    return {"job_id": job.id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: CurrentUser):
    job = jobs.get(job_id, user_id(user))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found (it may have expired)")
    return job.to_dict()


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str, user: CurrentUser):
    return load_meeting(meeting_id, user)


@router.put("/meetings/{meeting_id}/minutes")
def update_minutes(meeting_id: str, minutes: MeetingMinutes, user: CurrentUser):
    load_meeting(meeting_id, user)
    mongodb.update_meeting(meeting_id, user_id(user), {"minutes": minutes.model_dump()})
    return load_meeting(meeting_id, user)


@router.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: str, user: CurrentUser):
    load_meeting(meeting_id, user)
    mongodb.delete_meeting(meeting_id, user_id(user))
    warning = None
    if qdrant.is_configured():
        try:
            qdrant.delete_meeting_vectors(meeting_id)
        except Exception as e:  # the meeting is gone either way; report the leftover index
            logger.exception("Could not delete search vectors")
            warning = f"The meeting was deleted but its search index could not be cleaned up: {e}"
    return {"deleted": True, "warning": warning}


@router.get("/meetings/{meeting_id}/export/{fmt}")
def export_meeting(meeting_id: str, fmt: str, user: CurrentUser):
    if fmt not in EXPORTS:
        raise HTTPException(status_code=400, detail=f"Format must be one of: {', '.join(EXPORTS)}")
    meeting = load_meeting(meeting_id, user)
    media_type, render = EXPORTS[fmt]
    content = render(meeting)
    return Response(
        content=content.encode("utf-8") if isinstance(content, str) else content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_slug(meeting)}.{fmt}"'},
    )


class EmailRequest(BaseModel):
    recipients: str


@router.post("/meetings/{meeting_id}/email")
def email_meeting(meeting_id: str, body: EmailRequest, user: CurrentUser):
    meeting = load_meeting(meeting_id, user)
    if active_provider() is None:
        raise HTTPException(status_code=400, detail="Email isn't configured. Add SMTP settings or COMPOSIO_API_KEY to .env.")
    recipients, invalid = parse_recipients(body.recipients)
    if invalid:
        raise HTTPException(status_code=400, detail="Not valid email addresses: " + ", ".join(invalid))
    if not recipients:
        raise HTTPException(status_code=400, detail="Enter at least one email address.")
    return {"provider": active_provider(), "results": send_minutes_email(meeting, recipients)}


__all__ = ["router", "load_meeting", "file_slug", "InputError"]
