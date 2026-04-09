from __future__ import annotations

import json
from pathlib import Path

from app.auth.models import AuthState, GuestIdentity


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AuthState:
        if not self.path.exists():
            return AuthState()
        return AuthState.model_validate(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, state: AuthState) -> AuthState:
        self.path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return state

    def get_guest(self, guest_id: str) -> GuestIdentity | None:
        return self.load().guests.get(guest_id)
