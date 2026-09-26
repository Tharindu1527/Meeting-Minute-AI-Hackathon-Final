# utils/config.py
"""
Environment configuration.

Values come from a .env file or the process environment (e.g. a hosting
platform's secrets). Nothing here raises at import time: GET /api/status
reports `missing_required_vars()` and the frontend shows a setup screen
instead of the app crashing.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Keys the app cannot work without, with what they are used for
REQUIRED_VARS = {
    "GEMINI_API_KEY": "AI analysis, chat, search embeddings and audio summaries (free key: https://aistudio.google.com/apikey)",
    "MONGODB_URI": "saving meetings and minutes",
}

# Keys that unlock optional features
OPTIONAL_VARS = {
    "ASSEMBLYAI_API_KEY": "transcribing audio/video (uploaded or pasted transcripts work without it)",
    "QDRANT_URI": "semantic search in chat (chat falls back to keyword search over the transcript)",
    "APP_PASSWORD": "password-protecting the app",
    "SMTP_HOST": "sending minutes by email over SMTP",
    "COMPOSIO_API_KEY": "sending minutes by email through Composio's Gmail integration",
}

# Gemini models that are free of charge on the Gemini API free tier (checked September 2026).
# Each can be overridden in .env if Google renames or retires a model.
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_OPTIONS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_SIZE = 768
DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"
FALLBACK_TTS_MODEL = "gemini-3.8-flash-lite-tts"
# Used when the main model is overloaded (HTTP 503) or rate-limited. Free-tier quotas are
# per model (20 requests/day for gemini-3.8-flash), so each extra model adds daily capacity.
DEFAULT_FALLBACK_MODELS = "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite"
# 0 = pace each model to the free-tier limit Gemini reports in its rate-limit errors
# (learned automatically). Set a number to pace every chat model to that rate instead.
DEFAULT_REQUESTS_PER_MINUTE = 0

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Gemini's OpenAI-compatible endpoint, used for chat completions (CrewAI agents and the chatbot)
GEMINI_OPENAI_BASE_URL = f"{GEMINI_API_BASE}/openai/"


def get_setting(name, default=None):
    """Read an environment variable, stripping whitespace and stray quotes"""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().strip('"').strip("'")
    return value if value else default


def missing_required_vars():
    return [name for name in REQUIRED_VARS if not get_setting(name)]


def is_debug():
    return (get_setting("DEBUG", "") or "").lower() in ("1", "true", "yes")


def get_gemini_api_key():
    return get_setting("GEMINI_API_KEY")


def get_default_model():
    return get_setting("GEMINI_MODEL", DEFAULT_MODEL)


def get_embedding_model():
    return get_setting("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_tts_model():
    return get_setting("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)


def get_fallback_models():
    raw = get_setting("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS)
    return [model.strip() for model in raw.split(",") if model.strip()]


def get_requests_per_minute():
    """Fixed chat requests per minute per model; 0 means use the limits learned from Gemini"""
    try:
        return max(0, int(get_setting("GEMINI_REQUESTS_PER_MINUTE", DEFAULT_REQUESTS_PER_MINUTE)))
    except ValueError:
        return DEFAULT_REQUESTS_PER_MINUTE


def get_reasoning_effort():
    """Optional thinking level ("low", "medium", "high"); unset uses Gemini's default"""
    return get_setting("GEMINI_REASONING_EFFORT")


def get_assemblyai_api_key():
    return get_setting("ASSEMBLYAI_API_KEY")


def get_mongodb_uri():
    return get_setting("MONGODB_URI")


def get_mongodb_db_name():
    return get_setting("MONGODB_DB_NAME", "meeting_minutes")


def get_qdrant_uri():
    return get_setting("QDRANT_URI")


def get_qdrant_api_key():
    return get_setting("QDRANT_API_KEY")


def get_qdrant_collection():
    return get_setting("QDRANT_COLLECTION", "meeting_chunks")


def get_app_password():
    return get_setting("APP_PASSWORD")


def get_composio_api_key():
    return get_setting("COMPOSIO_API_KEY")


def get_email_settings():
    """Email configuration for SMTP and Composio providers"""
    return {
        "provider": (get_setting("EMAIL_PROVIDER", "") or "").lower(),  # "smtp", "composio" or "" for auto
        "smtp_host": get_setting("SMTP_HOST"),
        "smtp_port": int(get_setting("SMTP_PORT", "587")),
        "smtp_user": get_setting("SMTP_USER"),
        "smtp_password": get_setting("SMTP_PASSWORD"),
        "email_from": get_setting("EMAIL_FROM") or get_setting("SMTP_USER"),
        "composio_api_key": get_composio_api_key(),
        # The Composio user whose connected Gmail account sends the email (COMPOSIO_ENTITY_ID is the old name)
        "composio_user_id": get_setting("COMPOSIO_USER_ID") or get_setting("COMPOSIO_ENTITY_ID", "default"),
        # Optional: pick one Gmail connection when the user has several
        "composio_connected_account_id": get_setting("COMPOSIO_CONNECTED_ACCOUNT_ID"),
    }
