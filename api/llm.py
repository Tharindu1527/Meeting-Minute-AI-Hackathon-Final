# api/llm.py
"""
Google Gemini access.

- Chat goes through Gemini's OpenAI-compatible endpoint (the `openai` SDK
  pointed at Google's base URL), the same route the CrewAI agents use.
- Embeddings and speech use Gemini's native REST API, which exposes
  features the compatibility layer does not.

Every call goes through `call_with_fallback`, built for the free tier:
requests are paced to the per-minute quota, rate-limited calls wait as long
as Gemini asks, and an overloaded model falls back to another free model.
"""
import logging
import re
import threading
import time
from collections import defaultdict, deque

import requests
from openai import OpenAI

from utils.config import (
    EMBEDDING_SIZE,
    GEMINI_API_BASE,
    GEMINI_OPENAI_BASE_URL,
    get_default_model,
    get_embedding_model,
    get_fallback_models,
    get_gemini_api_key,
    get_reasoning_effort,
    get_requests_per_minute,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4          # per model
BACKOFF_SECONDS = 4       # first wait when Gemini gives no retry delay; doubles each attempt
MAX_RETRY_DELAY = 65      # never wait longer than this for one retry
SWITCH_AFTER_SECONDS = 15  # rate-limited for longer than this: try the next model instead of waiting
COOLDOWN_SECONDS = 60      # after giving up on a model, try the others first; doubles on repeated failures
MAX_COOLDOWN_SECONDS = 900
DAILY_COOLDOWN_SECONDS = 3600  # daily free quota used up: don't retry that model for an hour
REQUEST_TIMEOUT = 120      # seconds; a stalled request counts as "unavailable" and falls back
STALL_SECONDS = 30         # an "unavailable" error that took longer than this means the model is stalling
STICKY_SECONDS = 600       # after a fallback model works, keep using it first for this long
UNAVAILABLE_ATTEMPTS = 2   # tries on an overloaded model before moving to the next one

RATE_LIMITED, UNAVAILABLE = "rate-limited", "unavailable"

_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)\s*s|retryDelay['\"]?\s*:\s*['\"]([\d.]+)s", re.IGNORECASE)
_UNAVAILABLE_MARKERS = ("UNAVAILABLE", "ServiceUnavailable", "InternalServerError", "high demand", "overloaded",
                        "Timeout", "timed out", "APIConnectionError", "Could not reach")

_PER_MINUTE_QUOTA_RE = re.compile(r"PerMinute.*?quotaValue['\"]?\s*:\s*['\"]?(\d+)", re.DOTALL)

# Free-tier requests-per-minute limits observed in Gemini's 429 errors (September 2026).
# More are learned at runtime from the errors themselves.
KNOWN_REQUESTS_PER_MINUTE = {"gemini-3.8-flash": 5}

_chat_client = None

# model -> time.monotonic() until which it is tried last (it was recently overloaded or rate-limited)
_cooldowns = {}
# model -> consecutive times it was given up on (lengthens its cooldown)
_failures = {}
# model -> requests per minute to pace to
_learned_limits = dict(KNOWN_REQUESTS_PER_MINUTE)
# model -> time.monotonic() of its last successful request
_last_success = {}


def reset_state():
    """Forget cooldowns, failure counts, recent successes and learned limits (used by tests)"""
    _cooldowns.clear()
    _failures.clear()
    _last_success.clear()
    _learned_limits.clear()
    _learned_limits.update(KNOWN_REQUESTS_PER_MINUTE)


def _cool_down(model, seconds, escalate=True):
    if escalate:
        _failures[model] = _failures.get(model, 0) + 1
        seconds = min(seconds * 2 ** (_failures[model] - 1), MAX_COOLDOWN_SECONDS)
    _cooldowns[model] = time.monotonic() + seconds


def _learn_limit(model, error):
    """Remember a per-minute quota reported in a 429 error so later requests are paced to it"""
    match = _PER_MINUTE_QUOTA_RE.search(str(error))
    if match:
        _learned_limits[model] = int(match.group(1))


class GeminiError(Exception):
    """Raised when a Gemini REST call fails"""

    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class AllModelsUnavailable(Exception):
    """Every model in the fallback list was overloaded, rate-limited or out of daily quota"""

    def __init__(self, reasons):
        self.reasons = reasons
        details = ", ".join(f"{model} ({reason})" for model, reason in reasons.items())
        super().__init__(f"All Gemini models are unavailable right now: {details}")


class RequestRateLimiter:
    """
    Client-side cap on requests per minute for each model

    Shared by every session in this process (the quota belongs to the API key,
    not the user), so the app waits for a free slot instead of being rejected.
    """

    def __init__(self, clock=time.monotonic, sleep=None):
        self._clock = clock
        self._sleep = sleep
        self._calls = defaultdict(deque)
        self._lock = threading.Lock()

    def wait(self, model, per_minute):
        if not per_minute:
            return
        while True:
            with self._lock:
                now = self._clock()
                window = self._calls[model]
                while window and now - window[0] >= 60:
                    window.popleft()
                if len(window) < per_minute:
                    window.append(now)
                    return
                delay = 60 - (now - window[0]) + 0.5
            logger.info("Pacing %s to %s requests/minute: waiting %.0fs", model, per_minute, delay)
            (self._sleep or time.sleep)(delay)


_limiter = RequestRateLimiter()


def classify_error(error):
    """
    Returns:
        str|None: RATE_LIMITED, UNAVAILABLE (worth retrying), or None for other errors
    """
    status = getattr(error, "status_code", None) or getattr(error, "status", None)
    text = f"{type(error).__name__}: {error}"
    if status == 429 or "RESOURCE_EXHAUSTED" in text or "RateLimitError" in text:
        return RATE_LIMITED
    if status in (500, 502, 503, 504) or any(marker in text for marker in _UNAVAILABLE_MARKERS):
        return UNAVAILABLE
    return None


def is_timeout(error):
    text = f"{type(error).__name__}: {error}"
    return "Timeout" in text or "timed out" in text


def is_daily_quota(error):
    """True when the free tier's requests-per-day quota (not the per-minute one) is used up"""
    return "PerDay" in str(error)


def suggested_delay(error):
    """Seconds Gemini asked us to wait (from the error), or None"""
    if getattr(error, "retry_after", None):
        return float(error.retry_after)
    match = _RETRY_DELAY_RE.search(str(error))
    return float(match.group(1) or match.group(2)) if match else None


def chat_models(primary=None):
    """The model to use followed by its fallbacks, without duplicates"""
    primary = primary or get_default_model()
    return [primary] + [m for m in get_fallback_models() if m != primary]


def _ready_first(models):
    """
    Order models for the next request

    Models not cooling down come first, in the given order, except that a model
    that worked in the last few minutes goes to the front (while the preferred
    one is busy, don't rediscover that on every request). Cooling models go
    last, earliest recovery first.
    """
    now = time.monotonic()
    ready = [m for m in models if _cooldowns.get(m, 0) <= now]
    recent = [m for m in ready if now - _last_success.get(m, float("-inf")) < STICKY_SECONDS]
    if recent and recent[0] != ready[0]:
        # Prefer the preferred model only if it has also worked recently
        ready.remove(recent[0])
        ready.insert(0, recent[0])
    cooling = sorted((m for m in models if m not in ready), key=lambda m: _cooldowns[m])
    return ready + cooling


def call_with_fallback(call, models, requests_per_minute=None, attempts_per_model=MAX_ATTEMPTS):
    """
    Run call(model) with pacing, retries and model fallback

    Args:
        call: Function taking a model name and performing one request
        models: Models to try, in order of preference
        requests_per_minute: Pacing per model; None/0 uses the limits known or learned from Gemini's errors
        attempts_per_model: Tries per model before moving to the next one

    Returns:
        Whatever `call` returns
    """
    models = _ready_first(models)
    last_error = None
    reasons = {}  # model -> why it was given up on
    for index, model in enumerate(models):
        next_model = models[index + 1] if index + 1 < len(models) else None
        for attempt in range(1, attempts_per_model + 1):
            _limiter.wait(model, requests_per_minute or _learned_limits.get(model))
            started = time.monotonic()
            try:
                result = call(model)
                _cooldowns.pop(model, None)
                _failures.pop(model, None)
                _last_success[model] = time.monotonic()
                return result
            except Exception as error:
                kind = classify_error(error)
                if kind is None:
                    raise
                last_error = error
                if kind == RATE_LIMITED and is_daily_quota(error):
                    # Gemini still suggests a short retry delay here, but the quota only resets daily
                    _cool_down(model, DAILY_COOLDOWN_SECONDS, escalate=False)
                    reasons[model] = "daily free quota used up"
                    logger.warning("%s: daily free-tier quota used up; %s", model,
                                   f"switching to {next_model}" if next_model else "giving up")
                    break
                if kind == RATE_LIMITED:
                    _learn_limit(model, error)
                stalled = is_timeout(error) or time.monotonic() - started > STALL_SECONDS
                if next_model and kind == UNAVAILABLE and stalled:
                    # Overloaded models often hold a request for minutes before failing, and do it
                    # again on retry; move on instead of spending another full wait on it
                    _cool_down(model, COOLDOWN_SECONDS)
                    reasons[model] = "not responding"
                    logger.warning("%s stalled (%s); switching to %s", model, type(error).__name__, next_model)
                    break
                delay = suggested_delay(error) or BACKOFF_SECONDS * 2 ** (attempt - 1)
                busy_with_backup = next_model and kind == UNAVAILABLE and attempt >= UNAVAILABLE_ATTEMPTS
                if attempt == attempts_per_model or busy_with_backup or (next_model and delay > SWITCH_AFTER_SECONDS):
                    _cool_down(model, max(delay, COOLDOWN_SECONDS))
                    reasons[model] = "overloaded" if kind == UNAVAILABLE else "rate-limited"
                    logger.warning("%s is %s; %s", model, kind, f"switching to {next_model}" if next_model else "giving up")
                    break
                logger.warning("%s is %s; retrying in %.0fs", model, kind, min(delay, MAX_RETRY_DELAY))
                time.sleep(min(delay, MAX_RETRY_DELAY))
    if len(models) > 1:
        raise AllModelsUnavailable(reasons) from last_error
    raise last_error


def get_chat_client():
    """Shared OpenAI-SDK client for Gemini's OpenAI-compatible endpoint (retries are handled here, not by the SDK)"""
    global _chat_client
    if _chat_client is None:
        _chat_client = OpenAI(api_key=get_gemini_api_key(), base_url=GEMINI_OPENAI_BASE_URL,
                              max_retries=0, timeout=REQUEST_TIMEOUT)
    return _chat_client


def chat(messages, model=None):
    """
    Run a chat completion

    Temperature is left at Gemini's default: Google advises against lowering it for Gemini 3 models.

    Args:
        messages: List of {"role", "content"} dicts
        model: Model name (defaults to GEMINI_MODEL / gemini-3.8-flash)

    Returns:
        str: The model's reply
    """
    extra = {"reasoning_effort": get_reasoning_effort()} if get_reasoning_effort() else {}

    def attempt(model_name):
        response = get_chat_client().chat.completions.create(model=model_name, messages=messages, **extra)
        return response.choices[0].message.content or ""

    return call_with_fallback(attempt, chat_models(model), get_requests_per_minute())


def _error_details(response):
    """(message, retry delay in seconds) from a Gemini error response"""
    try:
        error = response.json().get("error", {})
    except ValueError:
        return response.text[:300], None
    retry_after = None
    for detail in error.get("details") or []:
        if str(detail.get("retryDelay", "")).endswith("s"):
            retry_after = float(detail["retryDelay"][:-1])
    return error.get("message") or response.text[:300], retry_after


def gemini_post(path, payload, timeout=60):
    """
    One POST to the native Gemini REST API (wrap in call_with_fallback for retries)

    Args:
        path: Path after /v1beta/, e.g. "models/gemini-embedding-2:embedContent"
        payload: JSON body

    Returns:
        dict: Parsed JSON response
    """
    url = f"{GEMINI_API_BASE}/{path}"
    headers = {"x-goog-api-key": get_gemini_api_key(), "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise GeminiError(f"Could not reach the Gemini API: {e}", status=503) from e
    if not response.ok:
        message, retry_after = _error_details(response)
        hint = " (free-tier rate limit reached; wait a minute and try again)" if response.status_code == 429 else ""
        raise GeminiError(f"Gemini API error {response.status_code}: {message}{hint}",
                          status=response.status_code, retry_after=retry_after)
    return response.json()


def embed(texts):
    """
    Embed texts for semantic search

    Sends one request per text: Gemini Embedding 2 merges several inputs in a
    single request into one combined vector. There is no model fallback here,
    since every vector in the index must come from the same model.

    Returns:
        list: One EMBEDDING_SIZE-dimensional vector per input text, in order
    """
    model = get_embedding_model()
    vectors = []
    for text in texts:
        payload = {"content": {"parts": [{"text": text}]}, "output_dimensionality": EMBEDDING_SIZE}
        data = call_with_fallback(lambda m: gemini_post(f"models/{m}:embedContent", payload), [model])
        embedding = data.get("embedding") or (data.get("embeddings") or [{}])[0]
        if not embedding.get("values"):
            raise GeminiError("Gemini returned no embedding")
        vectors.append(embedding["values"])
    return vectors
