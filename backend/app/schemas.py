"""Pydantic v2 request/response models. ORM objects are never returned from the API."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["hi", "mr", "ta", "en"]


class MerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_name: str
    city: str
    language: str


class LoginRequest(BaseModel):
    merchant_id: int


class TokenResponse(BaseModel):
    token: str
    merchant: MerchantOut


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    language: Lang = "hi"
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    decisions: dict[int, bool] | None = None
    voice_text: str | None = Field(default=None, max_length=300)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Lang = "hi"


class AudioOut(BaseModel):
    audio_url: str


class TranscriptOut(BaseModel):
    text: str
    language: str


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    reason: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    created_at: datetime


class BriefingOut(BaseModel):
    id: int
    language: str
    text: str
    audio_url: str | None
    facts: dict[str, Any]
    actions: list[ActionOut]


class KhataEntryIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    amount_rupees: int = Field(gt=0, le=500000)
    note: str = Field(default="", max_length=200)


class PayInfo(BaseModel):
    id: str
    merchant_name: str
    customer_name: str
    amount_paise: int
    status: str
    note: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    to_name: str
    to_phone: str
    body: str
    payment_link_id: str | None
    created_at: datetime
