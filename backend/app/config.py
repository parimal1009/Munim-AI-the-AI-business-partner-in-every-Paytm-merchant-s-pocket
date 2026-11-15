"""Application configuration, validated at startup (fail fast on missing secrets)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / "backend" / ".env"), extra="ignore"
    )

    database_url: str
    sarvam_api_key: str
    sarvam_model: str = "sarvam-105b"
    sarvam_stt_model: str = "saaras:v3"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "ritu"
    jwt_secret: str = Field(default="dev-only-change-me-munim-ai-secret-32b")
    jwt_ttl_minutes: int = 600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_web_url: str = "http://localhost:5173"
    audio_dir: Path = ROOT / "backend" / "data" / "audio"
    max_audio_bytes: int = 5 * 1024 * 1024
    enable_scheduler: bool = True
    briefing_hour: int = 8

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def psycopg_url(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
