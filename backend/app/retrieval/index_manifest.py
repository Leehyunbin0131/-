from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IndexedDocument(BaseModel):
    doc_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    vector: list[float] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class IndexManifest(BaseModel):
    embedding_provider: str
    embedding_model: str
    dimension: int
    documents: list[IndexedDocument] = Field(default_factory=list)


class IndexManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> IndexManifest | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return IndexManifest.model_validate(raw)

    def save(self, manifest: IndexManifest) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
