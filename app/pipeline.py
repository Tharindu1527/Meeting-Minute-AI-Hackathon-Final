# app/pipeline.py
"""
The meeting pipeline, independent of any UI:
source (recording, URL, transcript file or text) -> transcript -> AI crew -> saved meeting -> search index.
"""
import logging
import os

from api import assemblyai
from crews import AnalysisError, build_meeting_info, get_crew
from database import mongodb, qdrant
from utils.transcript import bound_for_llm, chunk_utterances, parse_transcript_file

logger = logging.getLogger(__name__)

SOURCES = ("recording", "url", "transcript_file", "text")


class InputError(Exception):
    """The request is incomplete or the input could not be read"""


def speaker_count(utterances):
    return len({u.get("speaker") for u in utterances if u.get("speaker")})


def read_transcript(source, *, file_path=None, filename=None, data=None, url=None, text=None,
                    speakers_expected=None, detect_language=True, redact_pii=False):
    """
    Turn any supported source into a transcript

    Args:
        source: "recording" (file_path), "url", "transcript_file" (filename + data) or "text"

    Returns:
        dict: {"text", "utterances", "language", "duration_seconds"}
    """
    if source in ("recording", "url"):
        if not assemblyai.is_configured():
            raise InputError("Transcribing recordings needs ASSEMBLYAI_API_KEY. You can upload or paste a transcript instead.")
        options = {"speakers_expected": speakers_expected or None,
                   "detect_language": detect_language, "redact_pii": redact_pii}
        if source == "url":
            if not (url or "").strip().startswith(("http://", "https://")):
                raise InputError("Enter a public http(s) link to the recording.")
            return assemblyai.transcribe_meeting(url.strip(), **options)
        if not file_path:
            raise InputError("Upload a recording.")
        return assemblyai.transcribe_meeting(file_path, **options)

    if source == "transcript_file":
        if data is None:
            raise InputError("Upload a transcript file.")
        parsed = parse_transcript_file(filename or "transcript.txt", data)
    elif source == "text":
        if not (text or "").strip():
            raise InputError("Paste the transcript text.")
        parsed = parse_transcript_file("pasted.txt", text)
    else:
        raise InputError(f"Unknown source '{source}'. Use one of: {', '.join(SOURCES)}")
    if not parsed["text"].strip():
        raise InputError("The transcript is empty.")
    return dict(parsed, language=None, duration_seconds=None)


def generate_meeting(title, meeting_date, source, *, owner_id, options, model=None, progress=None, cleanup_path=None,
                     **source_args):
    """
    Produce, save and index the minutes for one meeting

    Args:
        title: Meeting title
        meeting_date: datetime.date
        source: See read_transcript
        owner_id: The user the meeting belongs to
        options: {"fact_check", "research", "languages", "speakers_expected", "detect_language", "redact_pii"}
        model: Gemini model for the agents
        progress: Optional callback(message, done=None, total=None)
        cleanup_path: Temporary upload to delete once it has been transcribed
        **source_args: file_path / filename / data / url / text for read_transcript

    Returns:
        str: The new meeting id
    """
    report = progress or (lambda *args, **kwargs: None)
    try:
        if source in ("recording", "url"):
            report("Transcribing the recording. Long meetings can take a few minutes...")
        transcript = read_transcript(
            source, speakers_expected=options.get("speakers_expected"),
            detect_language=options.get("detect_language", True), redact_pii=options.get("redact_pii", False),
            **source_args,
        )
    finally:
        if cleanup_path and os.path.exists(cleanup_path):
            os.unlink(cleanup_path)
    report(f"Transcript ready ({len(transcript['text']):,} characters, {speaker_count(transcript['utterances'])} speakers)")

    llm_text, truncated = bound_for_llm(transcript["text"])
    crew = get_crew(model=model, fact_check=options.get("fact_check", False), research=options.get("research", False),
                    target_languages=options.get("languages") or [])
    result = crew.run_analysis(
        llm_text,
        build_meeting_info(title, meeting_date.isoformat(), transcript.get("language")),
        language_code=transcript.get("language"),
        progress=lambda done, total, label: report(label, done, total),
    )

    warnings = list(result.pop("warnings"))
    if truncated:
        warnings.insert(0, "The transcript was longer than the AI's input limit, so only the first part was analysed.")
    meeting = dict(
        result,
        title=title,
        meeting_date=meeting_date.isoformat(),
        options={"model": crew.model, "fact_check": options.get("fact_check", False),
                 "research": options.get("research", False), "languages": options.get("languages") or []},
        source={"type": source, "name": source_args.get("filename") or source_args.get("url")},
        transcript=dict(transcript, truncated=truncated),
        warnings=warnings,
    )
    meeting_id = mongodb.create_meeting(meeting, owner_id)
    report("Saved the minutes")

    if qdrant.is_configured():
        try:
            # Larger passages mean fewer embedding requests against the free-tier quota
            count = qdrant.index_meeting(meeting_id, title, chunk_utterances(transcript["utterances"], max_chars=2500))
            report(f"Indexed {count} transcript passage{'s' if count != 1 else ''} for search")
        except Exception as e:  # search indexing is optional; the minutes are already saved
            logger.exception("Indexing failed")
            mongodb.update_meeting(meeting_id, owner_id, {"warnings": warnings + [
                f"The transcript could not be indexed for chat search: {e}"]})
    return meeting_id


__all__ = ["AnalysisError", "InputError", "SOURCES", "generate_meeting", "read_transcript", "speaker_count"]
