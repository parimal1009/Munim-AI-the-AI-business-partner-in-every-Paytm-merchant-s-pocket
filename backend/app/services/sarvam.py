"""Sarvam AI wrapper: chat model factory, STT, TTS, with retries and typed errors."""
import base64
import logging
from functools import lru_cache
from pathlib import Path

from langchain_openai import ChatOpenAI
from sarvamai import SarvamAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core import UpstreamError

logger = logging.getLogger("sarvam")

LANG_CODES = {"hi": "hi-IN", "mr": "mr-IN", "ta": "ta-IN", "en": "en-IN", "te": "te-IN", "gu": "gu-IN"}


def _retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    return status in (429, 500, 502, 503) or isinstance(exc, (TimeoutError, ConnectionError))


_retry = retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.8, max=6),
    reraise=True,
)


@lru_cache
def _client() -> SarvamAI:
    return SarvamAI(api_subscription_key=get_settings().sarvam_api_key, timeout=60)


def chat_model(effort: str | None = None, max_tokens: int = 1500) -> ChatOpenAI:
    """Model router. Sarvam /v2 is OpenAI-compatible. effort=None disables reasoning (fast, cheap);
    pass "low" for planning-style tasks."""
    s = get_settings()
    return ChatOpenAI(
        model=s.sarvam_model,
        base_url="https://api.sarvam.ai/v2",
        api_key=s.sarvam_api_key,  # type: ignore[arg-type]
        max_tokens=max_tokens,
        reasoning_effort=effort or "none",
        timeout=45,
        max_retries=2,
    )


@_retry
def _chat_once(system: str, user: str, effort: str | None, max_tokens: int) -> str:
    llm = chat_model(effort, max_tokens)
    resp = llm.invoke([("system", system), ("human", user)])
    return str(resp.content).strip()


def complete(system: str, user: str, effort: str | None = None, max_tokens: int = 1200) -> str:
    try:
        return _chat_once(system, user, effort, max_tokens)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat failed: %s", type(exc).__name__)
        raise UpstreamError("Sarvam chat is unavailable") from exc


@_retry
def _stt_once(audio: bytes, filename: str, content_type: str, language: str) -> dict[str, str]:
    resp = _client().speech_to_text.transcribe(
        file=(filename, audio, content_type),
        model=get_settings().sarvam_stt_model,  # type: ignore[arg-type]
        mode="codemix",
        language_code=language,  # type: ignore[arg-type]
    )
    return {"text": resp.transcript or "", "language": str(getattr(resp, "language_code", "") or "")}


def transcribe(audio: bytes, filename: str, content_type: str, language: str = "unknown") -> dict[str, str]:
    try:
        return _stt_once(audio, filename, content_type, language)
    except Exception as exc:  # noqa: BLE001
        logger.warning("stt failed: %s", exc)
        raise UpstreamError("Speech recognition failed") from exc


def _split_text(text: str, limit: int = 450) -> list[str]:
    parts: list[str] = []
    cur = ""
    for sentence in text.replace("\n", " ").split("। "):
        for piece in sentence.split(". "):
            if len(cur) + len(piece) + 2 > limit and cur:
                parts.append(cur)
                cur = ""
            cur += piece.strip() + ". "
    if cur.strip():
        parts.append(cur.strip())
    return parts


@_retry
def _tts_once(text: str, lang_code: str) -> list[str]:
    s = get_settings()
    resp = _client().text_to_speech.convert(
        text=text,
        language_code=lang_code,  # type: ignore[arg-type]
        speaker=s.sarvam_tts_speaker,  # type: ignore[arg-type]
        model=s.sarvam_tts_model,  # type: ignore[arg-type]
        output_audio_codec="mp3",
    )
    return list(resp.audios)


def synthesize(text: str, lang: str, out_path: Path) -> Path:
    """Speak `text` and write an mp3 to out_path. Chunks are concatenated (mp3 frames are streamable)."""
    lang_code = LANG_CODES.get(lang, "hi-IN")
    try:
        data = b""
        for chunk in _split_text(text):
            for b64 in _tts_once(chunk, lang_code):
                data += base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        logger.warning("tts failed: %s", exc)
        raise UpstreamError("Speech synthesis failed") from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path

