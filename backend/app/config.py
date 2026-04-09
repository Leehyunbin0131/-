from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COUNSEL_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Career Counsel AI"
    app_version: str = "0.1.0"
    environment: str = "development"

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data_root: Path | None = None
    storage_root: Path | None = None

    default_llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-5.4-nano"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embedding_model: str = "embeddinggemma"
    request_timeout_seconds: float = 60.0

    default_top_k: int = 5
    parquet_preview_limit: int = 5
    frontend_app_url: str = "http://127.0.0.1:3000"
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:3000", "http://localhost:3000"])
    trial_turn_limit: int = 5
    paid_turn_pack_size: int = 30
    paid_pack_price_cents: int = 199
    paid_pack_currency: str = "usd"
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None
    email_verification_ttl_minutes: int = 15
    dev_return_email_code: bool = True
    guest_cookie_name: str = "counsel_guest_id"
    user_cookie_name: str = "counsel_user_id"
    cookie_secure: bool = False

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    def model_post_init(self, __context: object) -> None:
        if self.data_root is None:
            self.data_root = self.project_root / "Data"
        if self.storage_root is None:
            self.storage_root = self.project_root / "storage"

    @property
    def catalog_path(self) -> Path:
        return self.storage_root / "catalog" / "manifest.json"

    @property
    def retrieval_index_path(self) -> Path:
        return self.storage_root / "retrieval" / "index.json"

    @property
    def duckdb_path(self) -> Path:
        return self.storage_root / "query" / "warehouse.duckdb"

    @property
    def answer_trace_path(self) -> Path:
        return self.storage_root / "audit" / "answer_traces.jsonl"

    @property
    def sessions_root(self) -> Path:
        return self.storage_root / "sessions"

    @property
    def auth_state_path(self) -> Path:
        return self.storage_root / "auth" / "state.json"

    @property
    def usage_state_path(self) -> Path:
        return self.storage_root / "usage" / "state.json"

    @property
    def billing_state_path(self) -> Path:
        return self.storage_root / "billing" / "state.json"

    def ensure_storage_dirs(self) -> None:
        for path in (
            self.storage_root / "catalog",
            self.storage_root / "retrieval",
            self.storage_root / "query",
            self.storage_root / "audit",
            self.storage_root / "sessions",
            self.storage_root / "silver",
            self.storage_root / "auth",
            self.storage_root / "usage",
            self.storage_root / "billing",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage_dirs()
    return settings
