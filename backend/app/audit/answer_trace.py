from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnswerTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=utc_now)
    session_id: str | None = None
    provider: str
    model: str
    question: str
    intent: str
    datasets: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    answer: str


class AnswerTraceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, trace: AnswerTrace) -> AnswerTrace:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return trace
