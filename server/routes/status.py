# server/routes/status.py
"""Public endpoint: app configuration, service status and how accounts are created"""
import time

from fastapi import APIRouter

from api import assemblyai
from api.email_service import active_provider
from api.tts import VOICES
from crews import LANGUAGES
from database import mongodb, qdrant
from server.routes.auth import signup_open
from utils.config import (
    MODEL_OPTIONS,
    OPTIONAL_VARS,
    REQUIRED_VARS,
    get_default_model,
    get_signup_code,
    is_signup_allowed,
    missing_required_vars,
)

router = APIRouter(tags=["status"])

# An unreachable database would otherwise stall every status request for the connection timeout
_DB_STATUS_TTL = 30
_db_status = {"checked_at": 0.0, "ok": False, "error": None}


def database_status():
    if time.time() - _db_status["checked_at"] > _DB_STATUS_TTL:
        ok, error = mongodb.ping()
        _db_status.update(checked_at=time.time(), ok=ok, error=error)
    return _db_status["ok"], _db_status["error"]


@router.get("/status")
def status():
    missing = missing_required_vars()
    db_ok, db_error = database_status() if "MONGODB_URI" not in missing else (False, "MONGODB_URI is not set")
    default_model = get_default_model()
    models = MODEL_OPTIONS if default_model in MODEL_OPTIONS else [default_model] + MODEL_OPTIONS
    email = active_provider()
    return {
        "version": "3.0",
        "auth": {
            "signup_open": signup_open() if db_ok else is_signup_allowed(),
            "invite_code_required": bool(get_signup_code()),
            "password_reset": bool(email),
        },
        "missing_config": [{"name": name, "purpose": REQUIRED_VARS[name]} for name in missing],
        "optional_config": [{"name": name, "purpose": purpose} for name, purpose in OPTIONAL_VARS.items()],
        "services": {
            "database": {"ok": db_ok, "detail": "connected" if db_ok else (db_error or "unreachable")},
            "transcription": {"ok": assemblyai.is_configured(),
                              "detail": "AssemblyAI" if assemblyai.is_configured() else "off: transcripts only"},
            "search": {"ok": qdrant.is_configured(),
                       "detail": "semantic (Qdrant)" if qdrant.is_configured() else "keyword"},
            "email": {"ok": bool(email), "detail": email.upper() if email else "off"},
        },
        "models": models,
        "default_model": default_model,
        "languages": LANGUAGES,
        "voices": VOICES,
    }
