"""Classify a spoken reply as approve / reject. Keywords first (deterministic), LLM only if ambiguous."""
from typing import Literal

from pydantic import BaseModel

from app.services import sarvam

YES = ("haan", "han ", "haa", "ha ", "yes", "yeah", "ok", "okay", "kar do", "karo", "theek", "thik", "bhej do", "bhejo",
       "approve", "sure", "हाँ", "हां", "हा ", "जी", "ठीक", "कर दो", "करो", "भेज दो", "भेजो", "होय", "सरी", "ஆம்")
NO = ("nahi", "nahin", "no", "mat ", "cancel", "ruko", "stop", "नहीं", "नही", "मत", "रुको", "नको", "வேண்டாம்")


class Verdict(BaseModel):
    decision: Literal["approve", "reject", "unclear"]


def classify(text: str) -> bool | None:
    t = f" {text.strip().lower()} "
    if any(n in t for n in NO):
        return False
    if any(y in t for y in YES):
        return True
    try:
        v = sarvam.chat_model().with_structured_output(Verdict).invoke(
            f"The shopkeeper was asked to approve actions. Their reply: '{text}'. Is it approve, reject or unclear?")
        assert isinstance(v, Verdict)
        return {"approve": True, "reject": False}.get(v.decision)
    except Exception:  # noqa: BLE001
        return None
