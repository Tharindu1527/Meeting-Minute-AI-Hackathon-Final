# api/assemblyai.py
import logging

import assemblyai as aai

from utils.config import get_assemblyai_api_key
from utils.transcript import format_utterances

logger = logging.getLogger(__name__)

# File types AssemblyAI accepts that are common for meeting recordings
AUDIO_VIDEO_TYPES = ["mp3", "wav", "m4a", "mp4", "mov", "webm", "ogg", "flac", "aac", "mkv"]

# Personal data to redact when PII redaction is on. Person names are deliberately kept,
# otherwise attendees and action item owners could not be identified.
PII_POLICIES = [
    aai.PIIRedactionPolicy.phone_number,
    aai.PIIRedactionPolicy.email_address,
    aai.PIIRedactionPolicy.credit_card_number,
    aai.PIIRedactionPolicy.credit_card_cvv,
    aai.PIIRedactionPolicy.credit_card_expiration,
    aai.PIIRedactionPolicy.banking_information,
    aai.PIIRedactionPolicy.us_social_security_number,
    aai.PIIRedactionPolicy.passport_number,
    aai.PIIRedactionPolicy.drivers_license,
    aai.PIIRedactionPolicy.password,
]


class TranscriptionError(Exception):
    """Raised when AssemblyAI cannot transcribe the recording"""


def is_configured():
    return bool(get_assemblyai_api_key())


def transcribe_meeting(source, speakers_expected=None, detect_language=True, redact_pii=False):
    """
    Transcribe a meeting recording with speaker labels and timestamps

    Args:
        source: Local file path or a public URL to the audio/video file
        speakers_expected: Number of speakers if known (None lets AssemblyAI decide)
        detect_language: Detect the spoken language instead of assuming English
        redact_pii: Replace phone numbers, emails, card numbers etc. with placeholders

    Returns:
        dict: {"text", "utterances", "language", "duration_seconds"}
    """
    if not is_configured():
        raise TranscriptionError("ASSEMBLYAI_API_KEY is not set")

    aai.settings.api_key = get_assemblyai_api_key()
    config = aai.TranscriptionConfig(
        speaker_labels=True,
        speakers_expected=speakers_expected or None,
        language_detection=detect_language,
        punctuate=True,
        format_text=True,
    )
    if redact_pii:
        config.set_redact_pii(
            policies=PII_POLICIES,
            substitution=aai.PIISubstitutionPolicy.entity_name,
        )

    logger.info("Transcribing %s", source)
    transcript = aai.Transcriber(config=config).transcribe(source)

    if transcript.status == aai.TranscriptStatus.error:
        raise TranscriptionError(transcript.error or "Unknown transcription error")
    if not transcript.text:
        raise TranscriptionError("No speech was detected in the recording")

    utterances = [
        {"speaker": f"Speaker {u.speaker}", "start_ms": u.start, "end_ms": u.end, "text": u.text}
        for u in (transcript.utterances or [])
    ]
    if not utterances:
        utterances = [{"speaker": None, "start_ms": None, "end_ms": None, "text": transcript.text}]

    return {
        "text": format_utterances(utterances),
        "utterances": utterances,
        "language": (transcript.json_response or {}).get("language_code"),
        "duration_seconds": transcript.audio_duration,
    }
