# utils/transcript.py
"""
Transcript helpers: formatting speaker utterances, parsing uploaded
transcript files (.txt, .vtt, .srt), chunking for semantic search and
bounding transcript size for the LLM.

An utterance is a dict: {"speaker": str, "start_ms": int|None, "end_ms": int|None, "text": str}
"""
import re

# ~75k tokens: leaves room in a 128k-context model for instructions and upstream task outputs.
# A one-hour meeting is roughly 50-60k characters, so this covers ~5 hours of speech.
MAX_TRANSCRIPT_CHARS = 300_000

_TIMESTAMP_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
# A leading timestamp on a plain-text transcript line: "[00:02]", "(1:02:03)", "00:02 - " or "00:02 Name:".
# A bare time followed by ordinary text ("10:30 is when we start") is left alone.
_CLOCK = r"(?:(\d+):)?(\d{1,2}):(\d{2})"
_LINE_TIMESTAMP_RE = re.compile(
    rf"^(?:[\[(]{_CLOCK}[\])]\s*|{_CLOCK}\s*[-–]\s*|{_CLOCK}\s+(?=[A-Z][\w .'-]{{0,40}}?:\s))"
)
_SPEAKER_PREFIX_RE = re.compile(r"^([A-Z][\w .'-]{0,40}?):\s+(.+)$")
_VTT_VOICE_RE = re.compile(r"^<v(?:\.[^ >]*)?\s+([^>]+)>(.*?)(?:</v>)?$")


def format_timestamp(ms):
    """Format milliseconds as H:MM:SS or MM:SS"""
    if ms is None:
        return ""
    seconds = int(ms) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_utterances(utterances):
    """Render utterances as '[MM:SS] Speaker: text' lines"""
    lines = []
    for utterance in utterances:
        stamp = format_timestamp(utterance.get("start_ms"))
        prefix = f"[{stamp}] " if stamp else ""
        speaker = utterance.get("speaker")
        speaker_part = f"{speaker}: " if speaker else ""
        lines.append(f"{prefix}{speaker_part}{utterance['text'].strip()}")
    return "\n".join(lines)


def _parse_timestamp(value):
    match = _TIMESTAMP_RE.search(value)
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    millis = int(fraction.ljust(3, "0"))
    return ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + millis


def _split_speaker(text):
    """Pull a speaker out of '<v Name>text' (VTT) or 'Name: text'"""
    voice = _VTT_VOICE_RE.match(text)
    if voice:
        return voice.group(1).strip(), voice.group(2).strip()
    prefixed = _SPEAKER_PREFIX_RE.match(text)
    if prefixed:
        return prefixed.group(1).strip(), prefixed.group(2).strip()
    return None, text


def parse_subtitles(content):
    """Parse WebVTT or SRT content into utterances, merging consecutive cues by the same speaker"""
    utterances = []
    blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue  # WEBVTT header, NOTE blocks, etc.
        start_raw, _, end_raw = lines[timing_index].partition("-->")
        text = " ".join(lines[timing_index + 1:])
        text = re.sub(r"</?(?!v\b)[^>]+>", "", text).strip()  # drop styling tags but keep <v Speaker>
        if not text:
            continue
        speaker, text = _split_speaker(text)
        start_ms, end_ms = _parse_timestamp(start_raw), _parse_timestamp(end_raw)
        previous = utterances[-1] if utterances else None
        if previous and speaker and previous["speaker"] == speaker:
            previous["text"] += " " + text
            previous["end_ms"] = end_ms
        else:
            utterances.append({"speaker": speaker, "start_ms": start_ms, "end_ms": end_ms, "text": text})
    return utterances


def parse_plain_text(content):
    """
    Turn a pasted or .txt transcript into utterances

    Keeps 'Name: text' speaker prefixes and leading timestamps such as
    '[00:02] Name: text' (the format this app displays).
    """
    utterances = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        start_ms = None
        stamp = _LINE_TIMESTAMP_RE.match(line)
        if stamp and stamp.end() < len(line):
            groups = stamp.groups()
            # three alternatives, three (hours, minutes, seconds) groups each: use the one that matched
            hours, minutes, seconds = next(groups[i:i + 3] for i in (0, 3, 6) if groups[i + 1] is not None)
            start_ms = ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000
            line = line[stamp.end():]
        speaker, text = _split_speaker(line)
        utterances.append({"speaker": speaker, "start_ms": start_ms, "end_ms": None, "text": text})
    return utterances


def parse_transcript_file(filename, data):
    """
    Parse an uploaded transcript file

    Args:
        filename: Original file name (extension decides the parser)
        data: File content as bytes or str

    Returns:
        dict: {"text": formatted transcript, "utterances": list}
    """
    content = data.decode("utf-8-sig", errors="replace") if isinstance(data, bytes) else data
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if extension in ("vtt", "srt"):
        utterances = parse_subtitles(content)
    else:
        utterances = parse_plain_text(content)
    return {"text": format_utterances(utterances), "utterances": utterances}


def bound_for_llm(text, max_chars=MAX_TRANSCRIPT_CHARS):
    """
    Cap transcript size for the LLM

    Returns:
        tuple: (text, was_truncated)
    """
    if len(text) <= max_chars:
        return text, False
    cut = text.rfind("\n", 0, max_chars)
    return text[:cut if cut > 0 else max_chars], True


def chunk_utterances(utterances, max_chars=1200):
    """
    Group consecutive utterances into chunks for semantic search

    Returns:
        list: [{"text", "start_ms", "end_ms"}]
    """
    chunks, current, current_len = [], [], 0

    def flush():
        if current:
            chunks.append({
                "text": format_utterances(current),
                "start_ms": current[0].get("start_ms"),
                "end_ms": current[-1].get("end_ms"),
            })

    for utterance in utterances:
        pieces = _split_long_text(utterance["text"], max_chars)
        for piece in pieces:
            item = dict(utterance, text=piece)
            if current and current_len + len(piece) > max_chars:
                flush()
                current, current_len = [], 0
            current.append(item)
            current_len += len(piece)
    flush()
    return chunks


def _split_long_text(text, max_chars):
    """Split text longer than max_chars on sentence boundaries (hard-splitting very long sentences)"""
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, current = [], ""
    for sentence in sentences:
        while len(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def split_text(text, max_chars):
    """Public wrapper used by TTS: split text into pieces no longer than max_chars"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces, current = [], ""
    for paragraph in paragraphs:
        for part in _split_long_text(paragraph, max_chars):
            if current and len(current) + 2 + len(part) > max_chars:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        pieces.append(current)
    return pieces
