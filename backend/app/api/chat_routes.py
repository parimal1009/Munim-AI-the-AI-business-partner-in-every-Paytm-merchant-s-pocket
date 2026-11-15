"""Chat (SSE), voice STT/TTS. The graph runs here; approvals resume it via interrupt()."""
import json
import logging
import secrets
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from sqlalchemy import select

from app.agents.runtime import get_graph
from app.auth import MerchantId
from app.config import get_settings
from app.core import AppError, NotFoundError, rate_limit
from app.db import session_scope
from app.models import AgentEvent
from app.schemas import AudioOut, ChatRequest, ResumeRequest, SpeakRequest, TranscriptOut
from app.services import sarvam, voice_intent

router = APIRouter(prefix="/api")
logger = logging.getLogger("chat")
ALLOWED_AUDIO = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/aac"}


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _drive(graph_input: Any, config: dict[str, Any], thread_id: str) -> Iterator[str]:
    graph = get_graph()
    yield _sse({"type": "start", "thread_id": thread_id})
    try:
        for mode, chunk in graph.stream(graph_input, config, stream_mode=["custom", "updates"]):
            if mode == "custom":
                yield _sse(chunk)
            elif mode == "updates" and "__interrupt__" in chunk:
                payload = chunk["__interrupt__"][0].value
                yield _sse({"type": "interrupt", "thread_id": thread_id, "actions": payload["actions"]})
        state = graph.get_state(config)
        if not state.next:
            yield _sse({"type": "final", "thread_id": thread_id, "reply": state.values.get("reply", ""),
                        "agent": state.values.get("agent"), "language": state.values.get("language", "hi")})
    except Exception as exc:  # noqa: BLE001
        logger.exception("graph run failed")
        yield _sse({"type": "error", "message": "Munim hit a problem. Please try again.", "detail": type(exc).__name__})
    yield _sse({"type": "done"})


def _headers() -> dict[str, str]:
    return {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/chat")
def chat(body: ChatRequest, mid: int = MerchantId) -> StreamingResponse:
    rate_limit(f"chat:{mid}", 20)
    thread_id = body.thread_id or uuid.uuid4().hex[:16]
    config = {"configurable": {"merchant_id": mid, "thread_id": thread_id}}
    return StreamingResponse(
        _drive({"question": body.message, "language": body.language}, config, thread_id),
        media_type="text/event-stream", headers=_headers(),
    )


@router.post("/chat/resume")
def chat_resume(body: ResumeRequest, mid: int = MerchantId) -> StreamingResponse:
    rate_limit(f"chat:{mid}", 30)
    with session_scope() as s:  # thread must belong to this merchant
        owned = s.scalar(select(AgentEvent.id).where(AgentEvent.thread_id == body.thread_id, AgentEvent.merchant_id == mid).limit(1))
    if not owned:
        raise NotFoundError("Conversation not found")
    config = {"configurable": {"merchant_id": mid, "thread_id": body.thread_id}}
    state = get_graph().get_state(config)
    if not state.next:
        raise AppError("Nothing is waiting for approval")
    pending = [a["id"] for t in state.tasks for i in t.interrupts for a in i.value["actions"]]
    decisions = body.decisions
    if decisions is None and body.voice_text:
        verdict = voice_intent.classify(body.voice_text)
        if verdict is None:
            def unclear() -> Iterator[str]:
                yield _sse({"type": "clarify", "thread_id": body.thread_id, "message": "Samajh nahi aaya. 'Haan' ya 'Nahi' boliye."})
                yield _sse({"type": "done"})
            return StreamingResponse(unclear(), media_type="text/event-stream", headers=_headers())
        decisions = {i: verdict for i in pending}
    if decisions is None:
        raise AppError("Provide decisions or voice_text")
    decisions = {i: decisions.get(i, False) for i in pending}
    return StreamingResponse(
        _drive(Command(resume={"decisions": decisions}), config, body.thread_id),
        media_type="text/event-stream", headers=_headers(),
    )


@router.post("/voice/transcribe", response_model=TranscriptOut)
async def transcribe(audio: UploadFile = File(...), language: str = Form("unknown"), mid: int = MerchantId) -> TranscriptOut:
    rate_limit(f"voice:{mid}", 20)
    ctype = (audio.content_type or "").split(";")[0].lower()
    if ctype not in ALLOWED_AUDIO:
        raise AppError(f"Unsupported audio type: {ctype or 'unknown'}")
    data = await audio.read(get_settings().max_audio_bytes + 1)
    if len(data) > get_settings().max_audio_bytes:
        raise AppError("Audio too large (max 5 MB)")
    if len(data) < 800:
        raise AppError("Audio too short")
    res = sarvam.transcribe(data, audio.filename or "voice.webm", ctype, language)
    return TranscriptOut(**res)


@router.post("/voice/speak", response_model=AudioOut)
def speak(body: SpeakRequest, mid: int = MerchantId) -> AudioOut:
    rate_limit(f"tts:{mid}", 20)
    name = f"tts_{mid}_{secrets.token_hex(6)}.mp3"
    sarvam.synthesize(body.text, body.language, get_settings().audio_dir / name)
    return AudioOut(audio_url=f"/media/{name}")
