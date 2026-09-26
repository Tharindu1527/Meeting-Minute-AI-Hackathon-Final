# app/chatbot.py
"""
Question answering over meetings.

Relevant transcript excerpts are retrieved (Qdrant semantic search when
configured, keyword overlap otherwise) and passed to the model together
with the structured minutes, so answers can cite who said what and when.
"""
import logging
import re

from api.llm import chat
from app.export import minutes_to_markdown
from database import qdrant
from utils.transcript import chunk_utterances, format_timestamp

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 6
MAX_EXCERPTS = 6

SYSTEM_PROMPT = """You answer questions about company meetings using only the context provided.
Rules:
- Base every answer on the meeting minutes and transcript excerpts below. If they do not contain the answer, say so plainly.
- When you use a transcript excerpt, cite the meeting and timestamp like [Meeting title @ 12:30].
- Name people as they appear in the minutes' attendee list when possible.
- Be concise and specific."""

_WORD_RE = re.compile(r"[a-zA-Z0-9]{3,}")
_STOPWORDS = {"the", "and", "for", "with", "that", "this", "what", "who", "when", "where", "how", "did", "was",
              "were", "are", "about", "from", "they", "there", "which", "does", "have", "has", "been", "meeting"}


def _terms(text):
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def keyword_search(question, meetings, limit=MAX_EXCERPTS):
    """Rank transcript chunks by word overlap with the question (fallback when Qdrant is not configured)"""
    query_terms = _terms(question)
    scored = []
    for meeting in meetings:
        utterances = (meeting.get("transcript") or {}).get("utterances") or []
        for chunk in chunk_utterances(utterances):
            overlap = len(query_terms & _terms(chunk["text"]))
            if overlap:
                scored.append((overlap, dict(chunk, title=meeting.get("title", ""))))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def retrieve_excerpts(question, meetings, meeting_id=None):
    """
    Find transcript excerpts relevant to the question

    Args:
        question: The user's question
        meetings: Full meeting dicts in scope (used for the keyword fallback)
        meeting_id: Restrict semantic search to one meeting, or None for all

    Returns:
        list: [{"title", "text", "start_ms", ...}]
    """
    if qdrant.is_configured():
        try:
            return qdrant.search(question, meeting_id=meeting_id, limit=MAX_EXCERPTS)
        except Exception as e:  # fall back rather than failing the chat
            logger.warning("Semantic search failed, using keyword search: %s", e)
    return keyword_search(question, meetings)


def _format_excerpts(excerpts):
    blocks = []
    for excerpt in excerpts:
        stamp = format_timestamp(excerpt.get("start_ms"))
        header = f"{excerpt.get('title', '')} @ {stamp}" if stamp else excerpt.get("title", "")
        blocks.append(f"[{header}]\n{excerpt['text']}")
    return "\n\n".join(blocks) if blocks else "No matching transcript excerpts were found."


def answer_question(question, history, meetings, meeting_id=None, model=None):
    """
    Answer a question about one meeting or all meetings

    Args:
        question: The user's question
        history: Previous turns [{"role": "user"|"assistant", "content"}]
        meetings: Meeting dicts in scope (one meeting, or all meetings)
        meeting_id: The meeting in scope, or None for all meetings
        model: Chat model override

    Returns:
        dict: {"answer": str, "sources": list of excerpts}
    """
    excerpts = retrieve_excerpts(question, meetings, meeting_id)

    if meeting_id and meetings:
        minutes_context = minutes_to_markdown(meetings[0])
    else:
        minutes_context = "\n\n---\n\n".join(minutes_to_markdown(m) for m in meetings[:20])

    context = (
        f"MEETING MINUTES:\n{minutes_context}\n\n"
        f"RELEVANT TRANSCRIPT EXCERPTS:\n{_format_excerpts(excerpts)}"
    )
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context}"}]
    messages += [{"role": turn["role"], "content": turn["content"]} for turn in history[-MAX_HISTORY_TURNS * 2:]]
    messages.append({"role": "user", "content": question})

    return {"answer": chat(messages, model=model), "sources": excerpts}
