"""
Gemini integration tests against a local fake of Google's API.

A small HTTP server stands in for generativelanguage.googleapis.com, so the
real request path (CrewAI -> LiteLLM -> OpenAI SDK, and our REST calls) is
exercised without network access or an API key.
"""
import base64
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import agents.base
from api import llm, tts
from crews import build_meeting_info, get_crew
from fake_llm import TRANSCRIPT, answer_for
from utils.config import EMBEDDING_SIZE


def make_wav(samples, rate=24000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x01\x00" * samples)
    return buffer.getvalue()


class FakeGemini:
    """
    Records requests. `failures` makes the next N requests return 429 (with Gemini's
    retryDelay); models in `overloaded` always return 503.
    """

    def __init__(self):
        self.requests = []
        self.failures = 0
        self.overloaded = set()
        self.daily_exhausted = set()
        self.use_tools = False
        self.prompts = {}
        self.sleeps = []

    def handle(self, path, headers, body):
        self.requests.append({"path": path, "headers": headers, "body": body})
        if self.failures:
            self.failures -= 1
            return 429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                   "message": "You exceeded your current quota. Please retry in 7.2s.",
                                   "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]}}
        if body.get("model") in self.overloaded:
            return 503, {"error": {"code": 503, "status": "UNAVAILABLE",
                                   "message": "This model is currently experiencing high demand."}}
        if body.get("model") in self.daily_exhausted:
            return 429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                   "message": "Quota exceeded, limit: 20. Please retry in 35.9s.",
                                   "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                                       {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]},
                                       {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "35s"}]}}
        if path.endswith("/chat/completions"):
            if body["messages"][-1]["role"] == "assistant":  # real Gemini rejects these
                return 400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                       "message": "Requests ending with a model turn are not supported."}}
            text = "\n".join(m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
                             for m in body["messages"])
            if "Fact-check this meeting" in text and self.use_tools:
                content = self._fact_check_with_tool(body["messages"])
            else:
                try:
                    content = answer_for(text, self.prompts)
                except AssertionError:
                    content = "Priya owns the budget [Budget review @ 01:10]."
            return 200, {"id": "c1", "object": "chat.completion", "created": 0, "model": body["model"],
                         "choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant", "content": content}}],
                         "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
        if path.endswith(":embedContent"):
            return 200, {"embedding": {"values": [0.1] * body["output_dimensionality"]}}
        if path.endswith("/interactions"):
            audio = base64.b64encode(make_wav(1000)).decode()
            return 200, {"steps": [{"type": "user_input"},
                                   {"type": "model_output", "content": [{"type": "audio", "data": audio}]}]}
        return 404, {"error": {"message": f"unknown path {path}"}}

    @staticmethod
    def _fact_check_with_tool(messages):
        """First turn: call the Wikipedia tool. Once the tool result is in the conversation: answer."""
        # (The tool-format instructions themselves mention "Observation:", so look for an actual tool turn)
        if not any(m["role"] == "assistant" for m in messages):
            return ('Thought: I should check the Eiffel Tower claim.\n'
                    'Action: Wikipedia search\nAction Input: {"query": "Eiffel Tower"}')
        return "Thought: I now know the final answer\nFinal Answer: " + json.dumps({"claims": [{
            "claim": "The Eiffel Tower is in Berlin", "speaker": "Priya", "status": "Refuted",
            "explanation": "Wikipedia places the Eiffel Tower in Paris.",
            "sources": ["https://en.wikipedia.org/wiki/Eiffel_Tower"]}]})


@pytest.fixture
def fake_gemini(monkeypatch):
    fake = FakeGemini()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            status, payload = fake.handle(self.path, dict(self.headers), body)
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/v1beta"

    monkeypatch.setattr(llm, "GEMINI_API_BASE", base)
    monkeypatch.setattr(llm, "GEMINI_OPENAI_BASE_URL", f"{base}/openai/")
    monkeypatch.setattr(agents.base, "GEMINI_OPENAI_BASE_URL", f"{base}/openai/")
    monkeypatch.setattr(llm, "_chat_client", None)
    monkeypatch.setattr(llm, "_cooldowns", {})
    monkeypatch.setattr(llm.time, "sleep", fake.sleeps.append)
    yield fake
    server.shutdown()


def test_crew_runs_on_gemini_openai_compatible_endpoint(fake_gemini):
    fake_gemini.failures = 1  # the first call hits a free-tier rate limit and must be retried

    result = get_crew(model="gemini-3.8-flash").run_analysis(
        TRANSCRIPT, build_meeting_info("Budget review", "2026-09-25", "en"), language_code="en")

    assert result["warnings"] == []
    assert result["minutes"]["decisions"][0]["decision"] == "Freeze hiring until Q4"
    assert result["minutes"]["action_items"][0]["owner"] == "Ravi"

    chat_calls = [r for r in fake_gemini.requests if r["path"].endswith("/openai/chat/completions")]
    assert len(chat_calls) == 6  # 5 tasks + 1 retry after the 429
    assert {r["body"]["model"] for r in chat_calls} == {"gemini-3.8-flash"}
    assert {r["headers"]["Authorization"] for r in chat_calls} == {"Bearer test-key"}
    assert all("temperature" not in r["body"] for r in chat_calls)  # Gemini 3: keep the default
    assert fake_gemini.sleeps == [7.2]  # waited as long as Gemini asked ("retry in 7.2s")
    assert "Ravi here - marketing overspent" in fake_gemini.prompts["Produce the structured record"]


def test_tool_using_agent_respects_gemini_turn_rules(fake_gemini, monkeypatch):
    import agents.tools

    monkeypatch.setattr(agents.tools, "search_wikipedia", lambda query: [{
        "title": "Eiffel Tower", "extract": "The Eiffel Tower is a landmark in Paris, France.",
        "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"}])
    fake_gemini.use_tools = True

    result = get_crew(model="gemini-3.8-flash", fact_check=True).run_analysis(
        TRANSCRIPT, build_meeting_info("Budget review", "2026-09-25"))

    [claim] = result["fact_check"]["claims"]
    assert claim["status"] == "Refuted" and claim["sources"] == ["https://en.wikipedia.org/wiki/Eiffel_Tower"]
    fact_calls = [r["body"]["messages"] for r in fake_gemini.requests
                  if "Fact-check this meeting" in json.dumps(r["body"]["messages"])]
    assert len(fact_calls) == 2
    assert fact_calls[1][-1] == {"role": "user", "content": "Continue."}
    assert "landmark in Paris" in json.dumps(fact_calls[1])  # the tool result reached the model


def test_crew_falls_back_when_the_model_is_overloaded(fake_gemini):
    fake_gemini.overloaded = {"gemini-3.8-flash"}
    crew = get_crew(model="gemini-3.8-flash")

    result = crew.run_analysis(TRANSCRIPT, build_meeting_info("Budget review", "2026-09-25"))

    assert result["warnings"] == [] and result["minutes"]["summary"]
    models = [r["body"]["model"] for r in fake_gemini.requests]
    assert set(models) == {"gemini-3.8-flash", "gemini-3.5-flash"}
    assert models.count("gemini-3.5-flash") == 5  # every task completed on the fallback
    assert crew.agent("summarizer").create_agent().llm.model == "openai/gemini-3.8-flash"  # restored


def test_chatbot_chat_uses_gemini_and_retries(fake_gemini):
    fake_gemini.failures = 1
    answer = llm.chat([{"role": "user", "content": "Who owns the budget?"}], model="gemini-3.5-flash-lite")
    assert answer.startswith("Priya owns the budget")
    assert [r["body"]["model"] for r in fake_gemini.requests] == ["gemini-3.5-flash-lite"] * 2
    assert fake_gemini.sleeps == [7.2]


def test_chat_falls_back_through_every_model(fake_gemini):
    fake_gemini.overloaded = {"gemini-3.8-flash", "gemini-3.5-flash"}
    assert llm.chat([{"role": "user", "content": "Hi"}]).startswith("Priya owns")
    models = [r["body"]["model"] for r in fake_gemini.requests]
    assert models[-1] == "gemini-3.5-flash-lite"
    # an overloaded model gets one retry (after 4s) when a backup exists, then the next model is tried
    assert models.count("gemini-3.8-flash") == models.count("gemini-3.5-flash") == llm.UNAVAILABLE_ATTEMPTS
    assert fake_gemini.sleeps == [4, 4]

    # The overloaded models are now cooling down: the next call goes straight to the working one
    fake_gemini.requests.clear()
    llm.chat([{"role": "user", "content": "Hi again"}])
    assert [r["body"]["model"] for r in fake_gemini.requests] == ["gemini-3.5-flash-lite"]


def test_all_models_failing_explains_each_one(fake_gemini):
    from crews.base_crew import describe_failure

    fake_gemini.daily_exhausted = {"gemini-3.8-flash"}
    fake_gemini.overloaded = {"gemini-3.5-flash", "gemini-3.5-flash-lite"}
    with pytest.raises(llm.AllModelsUnavailable) as failure:
        llm.chat([{"role": "user", "content": "Hi"}])

    assert failure.value.reasons == {"gemini-3.8-flash": "daily free quota used up",
                                     "gemini-3.5-flash": "overloaded", "gemini-3.5-flash-lite": "overloaded"}
    message = describe_failure(failure.value)
    assert "gemini-3.5-flash (overloaded)" in message and "try again shortly" in message


def test_tts_reports_unavailable_models_as_tts_error(fake_gemini):
    fake_gemini.overloaded = {"gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"}
    with pytest.raises(tts.TTSError, match="All Gemini models are unavailable"):
        tts.text_to_speech("Hello")


def test_daily_quota_switches_model_without_waiting(fake_gemini):
    fake_gemini.daily_exhausted = {"gemini-3.8-flash"}
    assert llm.chat([{"role": "user", "content": "Hi"}]).startswith("Priya owns")
    assert [r["body"]["model"] for r in fake_gemini.requests] == ["gemini-3.8-flash", "gemini-3.5-flash"]
    assert fake_gemini.sleeps == []  # "retry in 35s" is ignored: the quota resets daily
    assert llm._cooldowns["gemini-3.8-flash"] - llm.time.monotonic() > 3000


def test_model_that_worked_is_tried_first_for_a_while(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = []
    busy = {"primary"}

    def call(model):
        calls.append(model)
        if model in busy:
            raise Exception("503 UNAVAILABLE high demand")
        return model

    assert llm.call_with_fallback(call, ["primary", "backup"]) == "backup"
    llm._cooldowns.clear()  # primary's cooldown has passed...
    busy.clear()            # ...and it has recovered
    calls.clear()
    assert llm.call_with_fallback(call, ["primary", "backup"]) == "backup"
    assert calls == ["backup"]  # no request wasted rediscovering the preferred model

    llm._last_success["backup"] -= llm.STICKY_SECONDS + 1  # after the sticky window, preference order returns
    assert llm.call_with_fallback(call, ["primary", "backup"]) == "primary"


def test_stalled_model_switches_immediately(monkeypatch):
    monkeypatch.setattr(llm, "_cooldowns", {})
    monkeypatch.setattr(llm.time, "sleep", lambda s: pytest.fail("should not wait on a stalled model"))
    calls = []

    def call(model):
        calls.append(model)
        if model == "slow-model":
            raise Exception("litellm.Timeout: APITimeoutError - Request timed out.")
        return "ok"

    assert llm.call_with_fallback(call, ["slow-model", "backup"]) == "ok"
    assert calls == ["slow-model", "backup"]
    assert "slow-model" in llm._cooldowns


def test_per_minute_limit_is_learned_from_the_error():
    error = Exception("429 RESOURCE_EXHAUSTED {'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', "
                      "'quotaDimensions': {'location': 'global', 'model': 'm'}, 'quotaValue': '15'}")
    llm._learn_limit("m", error)
    assert llm._learned_limits["m"] == 15
    assert llm.KNOWN_REQUESTS_PER_MINUTE["gemini-3.8-flash"] == 5


def test_cooldown_grows_when_a_model_keeps_failing(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    failing = lambda model: (_ for _ in ()).throw(Exception("503 UNAVAILABLE high demand")) if model == "bad" else "ok"
    remaining = []
    for _ in range(3):
        llm.call_with_fallback(failing, ["bad", "good"], attempts_per_model=1)
        remaining.append(llm._cooldowns["bad"] - llm.time.monotonic())
        llm._cooldowns["bad"] = 0  # let it be tried first again...
        llm._last_success.clear()  # ...rather than sticking with "good"
    assert remaining[0] < remaining[1] < remaining[2] <= llm.MAX_COOLDOWN_SECONDS


def test_rate_limiter_paces_requests():
    now = {"t": 0.0}
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    limiter = llm.RequestRateLimiter(clock=lambda: now["t"], sleep=sleep)
    for _ in range(3):
        limiter.wait("m", per_minute=2)
    assert len(slept) == 1 and 60 <= slept[0] <= 61
    limiter.wait("other-model", per_minute=2)  # separate quota per model
    assert len(slept) == 1


def test_error_classification_and_retry_delay():
    litellm_style = Exception("litellm.RateLimitError: 429 ... 'status': 'RESOURCE_EXHAUSTED' Please retry in 51.87s.")
    assert llm.classify_error(litellm_style) == llm.RATE_LIMITED
    assert llm.suggested_delay(litellm_style) == 51.87
    assert llm.suggested_delay(Exception("{'retryDelay': '12s'}")) == 12.0
    assert llm.classify_error(Exception("ServiceUnavailableError: 503 high demand")) == llm.UNAVAILABLE
    assert llm.classify_error(ValueError("bad request")) is None


def test_embeddings_one_request_per_text(fake_gemini):
    vectors = llm.embed(["first chunk", "second chunk"])

    assert [len(v) for v in vectors] == [EMBEDDING_SIZE, EMBEDDING_SIZE]
    assert [r["path"] for r in fake_gemini.requests] == ["/v1beta/models/gemini-embedding-2:embedContent"] * 2
    first = fake_gemini.requests[0]
    assert first["body"] == {"content": {"parts": [{"text": "first chunk"}]}, "output_dimensionality": EMBEDDING_SIZE}
    assert first["headers"]["x-goog-api-key"] == "test-key"


def test_rest_errors_explain_rate_limits(fake_gemini):
    fake_gemini.failures = 10
    with pytest.raises(llm.GeminiError, match="free-tier rate limit"):
        llm.embed(["text"])
    assert len(fake_gemini.requests) == llm.MAX_ATTEMPTS
    assert fake_gemini.sleeps == [7.0] * (llm.MAX_ATTEMPTS - 1)  # retryDelay read from the error details


def test_text_to_speech_joins_segments_into_one_wav(fake_gemini, monkeypatch):
    monkeypatch.setattr(tts, "MAX_CHARS_PER_REQUEST", 40)
    audio = tts.text_to_speech("First sentence of the minutes. Second sentence follows here. Third one.", voice="Puck")

    calls = [r for r in fake_gemini.requests if r["path"] == "/v1beta/interactions"]
    assert len(calls) == 2
    assert calls[0]["body"]["model"] == "gemini-3.8-flash-tts"
    assert calls[0]["body"]["generation_config"] == {"speech_config": [{"voice": "Puck"}]}
    with wave.open(io.BytesIO(audio)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getnframes()) == (24000, 1, 2000)


def test_merge_wav_accepts_raw_pcm():
    merged = tts.merge_wav([b"\x00\x00" * 500, make_wav(300)])
    with wave.open(io.BytesIO(merged)) as wav:
        assert wav.getnframes() == 800 and wav.getframerate() == 24000


def test_missing_audio_is_an_error():
    with pytest.raises(tts.TTSError):
        tts.extract_audio({"steps": [{"type": "model_output", "content": [{"type": "text", "text": "hi"}]}]})
