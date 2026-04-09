from __future__ import annotations

import json
from pathlib import Path

from app.auth.models import AuthState, EmailVerification, GuestIdentity, UserAccount


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

    def find_user_by_email(self, email: str) -> UserAccount | None:
        normalized = email.strip().lower()
        state = self.load()
        for user in state.users.values():
            if user.email.strip().lower() == normalized:
                return user
        return None

    def get_guest(self, guest_id: str) -> GuestIdentity | None:
        return self.load().guests.get(guest_id)

    def get_user(self, user_id: str) -> UserAccount | None:
        return self.load().users.get(user_id)

    def get_verification(self, email: str) -> EmailVerification | None:
        return self.load().verifications.get(email.strip().lower())
