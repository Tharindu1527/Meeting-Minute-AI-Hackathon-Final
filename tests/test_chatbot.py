from app import chatbot


def test_keyword_search_ranks_matching_chunks(sample_meeting):
    other = dict(sample_meeting, title="Other", transcript={"utterances": [
        {"speaker": "Ann", "start_ms": 0, "end_ms": 1, "text": "Office party planning."}]})
    results = chatbot.keyword_search("How much did marketing overspend?", [sample_meeting, other])
    assert results and results[0]["title"] == "Q3 budget review"
    assert "Marketing overspent" in results[0]["text"]


def test_answer_includes_minutes_excerpts_and_history(monkeypatch, sample_meeting):
    captured = {}

    def fake_chat(messages, model=None, temperature=0.2):
        captured["messages"] = messages
        return "Ravi said marketing overspent by 10% [Q3 budget review @ 00:40]."

    monkeypatch.setattr(chatbot, "chat", fake_chat)
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    sample_meeting["id"] = "m1"

    result = chatbot.answer_question("What about marketing?", history, [sample_meeting], meeting_id="m1")

    system = captured["messages"][0]["content"]
    assert "Freeze hiring until Q4" in system           # structured minutes
    assert "[Q3 budget review @ 00:05]" in system       # excerpt header: meeting + chunk start
    assert "[00:40] Ravi: Marketing overspent" in system  # per-line timestamps kept
    assert [m["role"] for m in captured["messages"]] == ["system", "user", "assistant", "user"]
    assert result["answer"].startswith("Ravi said") and result["sources"]
