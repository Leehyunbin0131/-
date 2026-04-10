from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from pydantic import Field
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

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-5.4-nano"
    openai_embedding_model: str = "text-embedding-3-small"
    request_timeout_seconds: float = 60.0
    # Responses API(파일 인풋·추론·웹검색)는 수 분 걸릴 수 있음. ReadTimeout 방지용(초).
    openai_responses_timeout_seconds: float = 900.0
    openai_reasoning_effort: str = "medium"
    openai_file_batch_size: int = 10
    # 모집결과 파일 후보 상한(프로필 기준 정렬 후). LLM 배치·업로드 비용·지연을 줄입니다.
    openai_summary_max_candidate_files: int = 32
    # Responses API 전용. None이면 temperature 파라미터를 보내지 않음(gpt-5 등 일부 모델 필수).
    openai_responses_temperature: float | None = None

    # Web enrichment is used for living information such as dorms, tuition, and scholarships.
    openai_web_search_enabled: bool = True
    openai_web_search_model: str | None = None  # default: same as openai_chat_model

    frontend_app_url: str = "http://127.0.0.1:3000"
    # Comma-separated origins, or a JSON array string. Must stay `str` so pydantic-settings
    # does not call json.loads on an empty/malformed COUNSEL_API_CORS_ORIGINS env value.
    api_cors_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
    )
    trial_turn_limit: int = 5
    # 0이면 약 30턴 분량을 기준으로 follow-up 문맥을 유지합니다.
    followup_conversation_max_messages: int = 0
    guest_cookie_name: str = "counsel_guest_id"
    cookie_secure: bool = False

    def model_post_init(self, __context: object) -> None:
        if self.data_root is None:
            self.data_root = self.project_root / "Data"
        if self.storage_root is None:
            self.storage_root = self.project_root / "storage"

    def followup_context_message_limit(self) -> int:
        """후속 상담 LLM 입력에 넣는 대화 메시지 개수 상한(요약 assistant 포함)."""
        if self.followup_conversation_max_messages > 0:
            return self.followup_conversation_max_messages
        return 72

    @property
    def catalog_path(self) -> Path:
        return self.storage_root / "catalog" / "manifest.json"

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
    def openai_file_cache_path(self) -> Path:
        return self.storage_root / "llm" / "openai_file_cache.json"

    def ensure_storage_dirs(self) -> None:
        for path in (
            self.storage_root / "catalog",
            self.storage_root / "audit",
            self.storage_root / "sessions",
            self.storage_root / "silver",
            self.storage_root / "auth",
            self.storage_root / "usage",
            self.storage_root / "llm",
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def cors_allow_origins(self) -> list[str]:
        """Origins list for Starlette CORSMiddleware."""
        default = ["http://127.0.0.1:3000", "http://localhost:3000"]
        raw = (self.api_cors_origins or "").strip()
        if not raw:
            return default
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    return items if items else default
            except json.JSONDecodeError:
                return default
            return default
        items = [item.strip() for item in raw.split(",") if item.strip()]
        return items if items else default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage_dirs()
    return settings
