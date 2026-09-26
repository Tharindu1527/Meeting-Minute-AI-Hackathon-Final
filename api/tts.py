# api/tts.py
"""Text-to-speech with Gemini's TTS model (Interactions API), returned as one WAV file"""
import base64
import io
import logging
import wave

from api.llm import AllModelsUnavailable, GeminiError, call_with_fallback, gemini_post
from utils.config import FALLBACK_TTS_MODEL, get_tts_model
from utils.transcript import split_text

logger = logging.getLogger(__name__)

# A selection of Gemini's 30 prebuilt voices
VOICES = ["Kore", "Puck", "Charon", "Aoede", "Fenrir", "Leda", "Orus", "Zephyr"]

MAX_CHARS_PER_REQUEST = 3000

# Gemini TTS audio format: 24 kHz, 16-bit signed little-endian PCM, mono
SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS = 24000, 2, 1


class TTSError(Exception):
    """Raised when audio could not be generated"""


def text_to_speech(text, voice="Kore"):
    """
    Convert text to speech

    Long text is split on paragraph/sentence boundaries, each piece is spoken
    separately, and the pieces are joined into one WAV file.

    Args:
        text: Text to speak
        voice: One of VOICES (any Gemini prebuilt voice name works)

    Returns:
        bytes: WAV audio
    """
    if not text or not text.strip():
        raise TTSError("There is no text to convert to audio")

    models = list(dict.fromkeys([get_tts_model(), FALLBACK_TTS_MODEL]))
    segments = []
    try:
        for piece in split_text(text, MAX_CHARS_PER_REQUEST):
            request = {
                "input": [{"type": "user_input", "content": [{"type": "text", "text": piece}]}],
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": voice}]},
            }
            response = call_with_fallback(
                lambda model: gemini_post("interactions", dict(request, model=model), timeout=180), models)
            segments.append(extract_audio(response))
    except (GeminiError, AllModelsUnavailable) as e:
        logger.exception("Text-to-speech failed")
        raise TTSError(str(e)) from e

    return merge_wav(segments)


def extract_audio(response):
    """The decoded audio bytes from an Interactions API response"""
    for step in reversed(response.get("steps") or []):
        if step.get("type") != "model_output":
            continue
        for part in reversed(step.get("content") or []):
            if part.get("type") == "audio" and part.get("data"):
                return base64.b64decode(part["data"])
    raise TTSError("Gemini returned no audio")


def _read_pcm(audio):
    """
    PCM samples and format from a WAV file (or raw PCM in Gemini's default format)

    Returns:
        tuple: (pcm bytes, sample rate, sample width in bytes, channels)
    """
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return audio, SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS
    rate, width, channels, pcm = SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS, b""
    position = 12
    while position + 8 <= len(audio):
        chunk_id = audio[position:position + 4]
        size = int.from_bytes(audio[position + 4:position + 8], "little")
        body = audio[position + 8:position + 8 + size]
        if chunk_id == b"fmt ":
            channels = int.from_bytes(body[2:4], "little")
            rate = int.from_bytes(body[4:8], "little")
            width = int.from_bytes(body[14:16], "little") // 8
        elif chunk_id == b"data":
            pcm = body
        position += 8 + size + (size & 1)
    return pcm, rate, width, channels


def merge_wav(segments):
    """Join audio segments (WAV or raw PCM) into one WAV file"""
    parsed = [_read_pcm(segment) for segment in segments]
    _, rate, width, channels = parsed[0]
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        for pcm, *_ in parsed:
            wav.writeframes(pcm)
    return output.getvalue()
