"""
Runs the real CrewAI pipeline with the LLM replaced by a scripted fake.

This checks the things that used to be broken: every task sees the transcript
and its upstream outputs, structured outputs are collected from every task
(not just the last one), and nothing is filled in with made-up defaults.
"""
from types import SimpleNamespace

import pytest
from crewai import LLM

from crews import AnalysisError, build_meeting_info, get_crew
from crews.base_crew import describe_failure, structured_output
from crews.meeting_crew import MeetingCrew
from fake_llm import TRANSCRIPT, answer_for
from models import MeetingSummary


@pytest.fixture
def fake_llm(monkeypatch):
    prompts = {}

    def call(self, messages, *args, **kwargs):
        text = messages if isinstance(messages, str) else "\n".join(m["content"] for m in messages)
        return answer_for(text, prompts)

    monkeypatch.setattr(LLM, "call", call)
    return prompts


def test_crew_passes_inputs_and_collects_every_structured_output(fake_llm):
    steps_seen = []
    crew = get_crew(model="gemini-3.8-flash", fact_check=True, target_languages=["English", "Spanish"])

    result = crew.run_analysis(
        TRANSCRIPT, build_meeting_info("Budget review", "2026-09-25", "en"), language_code="en",
        progress=lambda done, total, label: steps_seen.append((done, total, label)),
    )

    minutes = result["minutes"]
    assert [a["name"] for a in minutes["attendees"]] == ["Priya", "Ravi"]
    assert minutes["decisions"][0]["decision"] == "Freeze hiring until Q4"
    assert minutes["summary"] == "The team agreed to freeze hiring until Q4."
    assert minutes["sentiment"]["overall_tone"] == "Constructive"
    item = minutes["action_items"][0]
    assert (item["owner"], item["due_date"], item["status"]) == ("Ravi", "2026-10-02", "Open") and item["id"]
    assert result["fact_check"] == {"claims": []}
    assert list(result["translations"]) == ["spanish"]  # English skipped: it is the meeting's language
    assert result["warnings"] == []

    # Every agent got what it needs
    assert "Ravi here - marketing overspent" in fake_llm["Identify everyone who spoke"]
    analysis_prompt = fake_llm["Produce the structured record"]
    assert "Ravi here - marketing overspent" in analysis_prompt and '"speaker_label": "Speaker A"' in analysis_prompt
    actions_prompt = fake_llm["Extract every action item"]
    assert "Meeting date: 2026-09-25" in actions_prompt and "Freeze hiring until Q4" in actions_prompt
    assert "Freeze hiring until Q4" in fake_llm["write the executive summary"]
    assert "freeze hiring" in fake_llm["Translate the meeting minutes"].lower()

    assert [label for _, _, label in steps_seen] == [
        "Identified attendees", "Mapped agenda, decisions and open issues", "Fact-checked claims",
        "Wrote the executive summary", "Assessed tone and dynamics", "Extracted action items", "Translated into Spanish"]
    assert steps_seen[-1][:2] == (7, 7)


def test_structured_output_falls_back_to_json_in_raw_text():
    task = SimpleNamespace(output=SimpleNamespace(
        pydantic=None, raw='Here you go: {"summary": "Short.", "highlights": []} Thanks'))
    assert structured_output(task, MeetingSummary) == MeetingSummary(summary="Short.", highlights=[])

    garbage = SimpleNamespace(output=SimpleNamespace(pydantic=None, raw="I could not do it"))
    assert structured_output(garbage, MeetingSummary) is None


@pytest.mark.parametrize("errors", ["strict", "surrogateescape"])
def test_crew_survives_a_windows_code_page_console(fake_llm, monkeypatch, errors):
    """CrewAI prints emoji; a cp1252 stdout (Windows pipe/legacy console) must not abort the run"""
    import io
    import sys

    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors=errors)
    monkeypatch.setattr(sys, "stdout", console)
    result = get_crew(model="gemini-3.8-flash").run_analysis(
        TRANSCRIPT, build_meeting_info("Budget review", "2026-09-25"))
    assert result["minutes"]["decisions"] and console.errors == "replace"


def test_lenient_schemas_accept_common_llm_variations():
    from models import ActionItemList, CheckedClaim, MeetingAnalysis, TrackedActionItem

    actions = ActionItemList.model_validate({"action_items": [{"task": "Send budget", "priority": "HIGH"}],
                                             "next_meeting": None})
    assert actions.action_items[0].priority == "High"
    assert TrackedActionItem(task="x", status="completed", id=None).status == "Done"
    assert TrackedActionItem(task="x", id=None).id  # a fresh id, never empty
    assert CheckedClaim(claim="c", status="Partially True", explanation="e", sources=None).status == "Partially verified"
    analysis = MeetingAnalysis.model_validate({"key_topics": None, "agenda_items": [{"title": "t", "discussion": None}],
                                               "decisions": [], "open_issues": None})
    assert analysis.key_topics == [] and analysis.agenda_items[0].discussion == ""


def test_unparseable_answer_is_repaired_once(fake_llm, monkeypatch):
    """A task whose answer isn't valid JSON gets one repair request instead of an empty section"""
    import crews.base_crew as base_crew

    original_answer_for = __import__("fake_llm").answer_for

    def call(self, messages, *args, **kwargs):
        text = messages if isinstance(messages, str) else "\n".join(m["content"] for m in messages)
        if "Assess the tone" in text:
            return "Thought: done\nFinal Answer: The mood was constructive and calm."  # prose, not JSON
        return original_answer_for(text, fake_llm)

    monkeypatch.setattr(LLM, "call", call)
    repairs = []

    def fake_chat(messages, model=None):
        repairs.append(messages[0]["content"])
        return '{"overall_tone": "Constructive", "summary": "The mood was constructive and calm."}'

    monkeypatch.setattr(base_crew, "chat", fake_chat)
    result = get_crew(model="gemini-3.8-flash").run_analysis(TRANSCRIPT, build_meeting_info("B", "2026-09-25"))

    assert result["warnings"] == []
    assert result["minutes"]["sentiment"]["overall_tone"] == "Constructive"
    assert len(repairs) == 1 and "The mood was constructive and calm." in repairs[0]


def test_rate_limit_failures_get_a_readable_message():
    assert "free-tier rate limit" in describe_failure(Exception("litellm.RateLimitError: 429 RESOURCE_EXHAUSTED"))
    assert describe_failure(ValueError("boom")) == "The AI analysis failed: boom"


def test_missing_steps_become_warnings_not_invented_content():
    steps = [(key, key.title(), None, None) for key in ("attendees", "analysis", "summary", "sentiment", "action_items")]
    results = dict.fromkeys(("attendees", "analysis", "sentiment", "action_items"))
    results["summary"] = MeetingSummary(summary="Only the summary worked.", highlights=[])

    assembled = MeetingCrew.assemble(results, steps)

    assert assembled["minutes"]["summary"] == "Only the summary worked."
    assert assembled["minutes"]["action_items"] == [] and assembled["minutes"]["decisions"] == []
    assert len(assembled["warnings"]) == 4

    with pytest.raises(AnalysisError):
        MeetingCrew.assemble(dict.fromkeys(("attendees", "analysis", "summary", "sentiment", "action_items")), steps)
