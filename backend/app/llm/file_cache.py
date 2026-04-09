from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OpenAIFileCacheRecord(BaseModel):
    file_hash: str
    file_id: str
    source_path: str
    filename: str
    uploaded_at: datetime = Field(default_factory=utc_now)


class OpenAIFileCacheState(BaseModel):
    records: dict[str, OpenAIFileCacheRecord] = Field(default_factory=dict)


class OpenAIFileCacheStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> OpenAIFileCacheState:
        if not self.path.exists():
            return OpenAIFileCacheState()
        return OpenAIFileCacheState.model_validate(
            json.loads(self.path.read_text(encoding="utf-8"))
        )

    def save(self, state: OpenAIFileCacheState) -> OpenAIFileCacheState:
        self.path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return state

    def get(self, file_hash: str) -> OpenAIFileCacheRecord | None:
        return self.load().records.get(file_hash)

    def put(self, record: OpenAIFileCacheRecord) -> OpenAIFileCacheRecord:
        state = self.load()
        state.records[record.file_hash] = record
        self.save(state)
        return record
