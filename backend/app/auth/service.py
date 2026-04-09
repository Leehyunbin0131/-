from __future__ import annotations

from fastapi import Request, Response

from app.auth.models import ActorContext, GuestIdentity, utc_now
from app.auth.store import AuthStore
from app.chat.models import CounselingSession
from app.config import Settings
from app.usage.models import ActorType


class AuthService:
    """Minimal guest-only identity service for session ownership and quota tracking."""

    def __init__(
        self,
        settings: Settings,
        store: AuthStore,
    ) -> None:
        self.settings = settings
        self.store = store

    def ensure_actor(self, request: Request, response: Response | None = None) -> ActorContext:
        guest_id = request.cookies.get(self.settings.guest_cookie_name)
        guest = self.store.get_guest(guest_id) if guest_id else None
        if guest is not None:
            guest.last_seen_at = utc_now()
            state = self.store.load()
            state.guests[guest.guest_id] = guest
            self.store.save(state)
            return ActorContext(
                actor_type=ActorType.guest,
                actor_id=guest.guest_id,
                guest_id=guest.guest_id,
            )

        if response is None:
            raise ValueError("No guest identity is available.")

        state = self.store.load()
        guest = GuestIdentity()
        state.guests[guest.guest_id] = guest
        self.store.save(state)
        self._set_guest_cookie(response, guest.guest_id)
        return ActorContext(
            actor_type=ActorType.guest,
            actor_id=guest.guest_id,
            guest_id=guest.guest_id,
        )

    def require_actor(self, request: Request) -> ActorContext:
        return self.ensure_actor(request, None)

    def register_session(self, actor: ActorContext, session_id: str) -> None:
        state = self.store.load()
        guest = state.guests.get(actor.guest_id)
        if guest is None:
            return
        if session_id not in guest.session_ids:
            guest.session_ids.append(session_id)
        guest.last_seen_at = utc_now()
        state.guests[guest.guest_id] = guest
        self.store.save(state)

    def assert_session_access(self, session: CounselingSession, actor: ActorContext) -> None:
        if session.guest_id == actor.guest_id:
            return
        raise ValueError("You do not have access to this counseling session.")

    def _set_guest_cookie(self, response: Response, guest_id: str) -> None:
        response.set_cookie(
            key=self.settings.guest_cookie_name,
            value=guest_id,
            httponly=True,
            samesite="lax",
            secure=self.settings.cookie_secure,
            max_age=60 * 60 * 24 * 30,
            path="/",
        )
