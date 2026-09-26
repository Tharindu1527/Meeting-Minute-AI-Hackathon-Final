# tests/conftest.py
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Deterministic settings: set before app modules import (python-dotenv never overrides existing variables)
os.environ.update({
    "GEMINI_API_KEY": "test-key",
    "GEMINI_MODEL": "",
    "GEMINI_REASONING_EFFORT": "",
    "GEMINI_REQUESTS_PER_MINUTE": "0",
    "GEMINI_FALLBACK_MODELS": "gemini-3.5-flash,gemini-3.5-flash-lite",
    "MONGODB_URI": "mongodb://test-host:27017",
    "MONGODB_DB_NAME": "test_meeting_minutes",
    "ASSEMBLYAI_API_KEY": "",
    "QDRANT_URI": "",
    "APP_PASSWORD": "",
    "EMAIL_PROVIDER": "",
    "SMTP_HOST": "",
    "SMTP_USER": "",
    "EMAIL_FROM": "",
    "COMPOSIO_API_KEY": "",
    "OTEL_SDK_DISABLED": "true",
    "CREWAI_DISABLE_TELEMETRY": "true",
})


@pytest.fixture(autouse=True)
def fresh_gemini_state():
    """Each test starts with no model cooldowns and no pacing (tests that need pacing set it up)"""
    from api import llm

    llm.reset_state()
    llm._learned_limits.clear()
    yield
    llm.reset_state()


@pytest.fixture
def mongo():
    """Point the database module at an in-memory mongomock client"""
    import mongomock

    from database import mongodb

    previous = mongodb._client
    mongodb._client = mongomock.MongoClient()
    yield mongodb
    mongodb._client = previous


@pytest.fixture
def sample_meeting():
    return {
        "title": "Q3 budget review",
        "meeting_date": "2026-09-24",
        "transcript": {
            "text": "[00:05] Priya: Welcome. Budget first.\n[00:40] Ravi: Marketing overspent by 10%.",
            "utterances": [
                {"speaker": "Priya", "start_ms": 5000, "end_ms": 9000, "text": "Welcome. Budget first."},
                {"speaker": "Ravi", "start_ms": 40000, "end_ms": 47000, "text": "Marketing overspent by 10%."},
            ],
            "duration_seconds": 1800,
            "language": "en",
        },
        "minutes": {
            "summary": "The team reviewed the Q3 budget & agreed to <freeze> hiring.",
            "highlights": ["Hiring freeze agreed"],
            "key_topics": ["Budget", "Hiring"],
            "attendees": [{"name": "Priya", "role": "Chair", "speaker_label": "Speaker A"},
                          {"name": "Ravi", "role": None, "speaker_label": "Speaker B"}],
            "agenda_items": [{"title": "Budget", "discussion": "Ravi reported overspend.", "outcome": "Freeze hiring"}],
            "decisions": [{"decision": "Freeze hiring until Q4", "decided_by": "Priya", "rationale": None}],
            "action_items": [
                {"id": "a1", "task": "Send revised budget", "owner": "Ravi", "due_date": "2026-09-30",
                 "priority": "High", "status": "Open", "context": None},
                {"id": "a2", "task": "Update hiring plan | pipeline", "owner": None, "due_date": None,
                 "priority": "Medium", "status": "Done", "context": None},
            ],
            "open_issues": ["Marketing spend cap"],
            "next_meeting": "2026-10-01",
            "sentiment": None,
        },
        "fact_check": None,
        "research": None,
        "translations": {},
        "warnings": [],
    }
