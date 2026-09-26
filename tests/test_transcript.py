from utils.transcript import (
    bound_for_llm,
    chunk_utterances,
    format_timestamp,
    format_utterances,
    parse_transcript_file,
    split_text,
)

VTT = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
<v Priya Shah>Good morning everyone.</v>

2
00:00:04.500 --> 00:00:06.000
<v Priya Shah>Let's start with the budget.</v>

3
00:01:02.000 --> 00:01:05.250
<v Ravi>Marketing is 10% over.</v>
"""

SRT = """1
00:00:01,000 --> 00:00:03,000
Priya: Welcome.

2
01:02:03,500 --> 01:02:05,000
Ravi: Thanks.
"""


def test_format_timestamp():
    assert format_timestamp(None) == ""
    assert format_timestamp(65_000) == "01:05"
    assert format_timestamp(3_723_000) == "1:02:03"


def test_parse_vtt_merges_consecutive_cues_by_speaker():
    parsed = parse_transcript_file("meeting.vtt", VTT.encode())
    assert [u["speaker"] for u in parsed["utterances"]] == ["Priya Shah", "Ravi"]
    first = parsed["utterances"][0]
    assert first["text"] == "Good morning everyone. Let's start with the budget."
    assert (first["start_ms"], first["end_ms"]) == (1000, 6000)
    assert parsed["text"].splitlines()[1] == "[01:02] Ravi: Marketing is 10% over."


def test_parse_srt_with_name_prefixes():
    parsed = parse_transcript_file("meeting.srt", SRT)
    assert [(u["speaker"], u["start_ms"]) for u in parsed["utterances"]] == [("Priya", 1000), ("Ravi", 3_723_500)]


def test_parse_plain_text_keeps_speakers_and_skips_blank_lines():
    parsed = parse_transcript_file("notes.txt", "Priya: Hello\n\nno speaker line\nRavi: Hi")
    assert [(u["speaker"], u["text"]) for u in parsed["utterances"]] == [
        ("Priya", "Hello"), (None, "no speaker line"), ("Ravi", "Hi")]
    assert parsed["text"] == "Priya: Hello\nno speaker line\nRavi: Hi"


def test_parse_plain_text_with_leading_timestamps():
    text = ("[00:02] Speaker A: Morning all.\n(1:02:03) Ravi: Budget update.\n00:40 - Amara: Worried.\n"
            "01:15 Daniel: Leads are up.\n10:30 is when we start")
    utterances = parse_transcript_file("pasted.txt", text)["utterances"]
    assert [(u["speaker"], u["start_ms"]) for u in utterances[:4]] == [
        ("Speaker A", 2000), ("Ravi", 3_723_000), ("Amara", 40_000), ("Daniel", 75_000)]
    assert utterances[1]["text"] == "Budget update."
    assert (utterances[4]["start_ms"], utterances[4]["text"]) == (None, "10:30 is when we start")  # plain text kept
    # Round trip: the app's own display format parses back to the same text
    assert parse_transcript_file("again.txt", format_utterances(utterances[:3]))["text"] == format_utterances(utterances[:3])


def test_bound_for_llm_cuts_on_line_boundary():
    text = "\n".join(f"line {i}" for i in range(100))
    bounded, truncated = bound_for_llm(text, max_chars=50)
    assert truncated and len(bounded) <= 50 and bounded.endswith(("line 6", "line 7"))
    assert bound_for_llm("short", max_chars=50) == ("short", False)


def test_chunk_utterances_respects_size_and_keeps_timestamps():
    utterances = [{"speaker": "A", "start_ms": i * 1000, "end_ms": i * 1000 + 900, "text": "word " * 60}
                  for i in range(10)]
    chunks = chunk_utterances(utterances, max_chars=700)
    assert len(chunks) > 1
    assert chunks[0]["start_ms"] == 0 and chunks[-1]["end_ms"] == 9900
    assert "".join(c["text"] for c in chunks).count("[") == 10  # every utterance kept once


def test_split_text_never_exceeds_limit():
    text = ("This is a sentence. " * 400) + "\n\n" + ("x" * 5000)
    pieces = split_text(text, 1000)
    assert all(len(p) <= 1000 for p in pieces)
    assert sum(len(p.replace(" ", "").replace("\n", "")) for p in pieces) == len(text.replace(" ", "").replace("\n", ""))
