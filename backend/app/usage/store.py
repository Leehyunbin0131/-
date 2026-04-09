from __future__ import annotations

import json
from pathlib import Path

from app.usage.models import UsageState


class UsageStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> UsageState:
        if not self.path.exists():
            return UsageState()
        return UsageState.model_validate(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, state: UsageState) -> UsageState:
        self.path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return state
