"""Scripted LLM answers shared by the crew tests"""
import json

TRANSCRIPT = (
    "[00:01] Speaker A: Good morning, I'm Priya and I'll chair today. First item is the {budget} review.\n"
    "[00:20] Speaker B: Thanks Priya. Ravi here - marketing overspent by 10 percent.\n"
    "[01:10] Speaker A: Agreed, we freeze hiring until Q4. Ravi, send the revised budget by next Friday.\n"
    "[01:30] Speaker B: Will do."
)

# Marker text found in each task's prompt -> the structured answer for that task
RESPONSES = {
    "Identify everyone who spoke": {"attendees": [
        {"name": "Priya", "role": "Chair", "speaker_label": "Speaker A"},
        {"name": "Ravi", "role": "Marketing", "speaker_label": "Speaker B"}]},
    "Produce the structured record": {
        "key_topics": ["Budget"],
        "agenda_items": [{"title": "Budget review", "discussion": "Ravi reported a 10% overspend.", "outcome": "Hiring freeze"}],
        "decisions": [{"decision": "Freeze hiring until Q4", "decided_by": "Priya", "rationale": "Overspend"}],
        "open_issues": ["Marketing spend cap"]},
    "Fact-check this meeting": {"claims": []},
    "write the executive summary": {"summary": "The team agreed to freeze hiring until Q4.", "highlights": ["Hiring freeze"]},
    "Assess the tone": {"overall_tone": "Constructive", "summary": "Calm and decisive.", "per_speaker": [],
                        "agreements": ["Hiring freeze"], "disagreements": []},
    "Extract every action item": {"action_items": [
        {"task": "Send the revised budget", "owner": "Ravi", "due_date": "2026-10-02", "priority": "High", "context": None}],
        "next_meeting": None},
    "Translate the meeting minutes": {"language": "Spanish", "summary": "El equipo acordó congelar las contrataciones.",
                                      "decisions": ["Congelar contrataciones hasta el Q4"], "action_items": ["Enviar presupuesto — Ravi"]},
}


def answer_for(prompt_text, seen=None):
    """The agent's final answer for a prompt, recording which task it was in `seen`"""
    for marker, payload in RESPONSES.items():
        if marker in prompt_text:
            if seen is not None:
                seen[marker] = prompt_text
            return f"Thought: I now know the final answer\nFinal Answer: {json.dumps(payload)}"
    raise AssertionError(f"Unexpected prompt: {prompt_text[:300]}")
