from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.auth.models import (
    ActorContext,
    EmailStartResponse,
    EmailVerification,
    GuestIdentity,
    UserAccount,
    UserResponse,
    utc_now,
)
from app.auth.store import AuthStore
from app.chat.models import CounselingSession
from app.chat.session_store import SessionStore
from app.config import Settings
from app.usage.models import ActorType
from app.usage.service import UsageService


class AuthService:
    def __init__(
        self,
        settings: Settings,
        store: AuthStore,
        session_store: SessionStore,
        usage_service: UsageService,
    ) -> None:
        self.settings = settings
        self.store = store
        self.session_store = session_store
        self.usage_service = usage_service

    def ensure_actor(self, request: Request, response: Response | None = None) -> ActorContext:
        user_id = request.cookies.get(self.settings.user_cookie_name)
        if user_id:
            user = self.store.get_user(user_id)
            if user is not None:
                return ActorContext(
                    actor_type=ActorType.user,
                    actor_id=user.user_id,
                    user_id=user.user_id,
                    user=user,
                    guest_id=request.cookies.get(self.settings.guest_cookie_name),
                )

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
            raise ValueError("No guest or user identity is available.")

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
        if actor.guest_id is None:
            return
        state = self.store.load()
        guest = state.guests.get(actor.guest_id)
        if guest is None:
            return
        if session_id not in guest.session_ids:
            guest.session_ids.append(session_id)
        guest.last_seen_at = utc_now()
        state.guests[guest.guest_id] = guest
        self.store.save(state)

    def start_email_verification(
        self,
        *,
        email: str,
        session_id: str | None,
        actor: ActorContext,
    ) -> EmailStartResponse:
        normalized = email.strip().lower()
        if not normalized:
            raise ValueError("Email must not be empty.")

        code = f"{secrets.randbelow(900000) + 100000}"
        verification = EmailVerification.create(
            email=normalized,
            code=code,
            ttl_minutes=self.settings.email_verification_ttl_minutes,
            session_id=session_id,
            guest_id=actor.guest_id,
        )
        state = self.store.load()
        state.verifications[normalized] = verification
        self.store.save(state)
        return EmailStartResponse(
            email=normalized,
            verification_code=code if self.settings.dev_return_email_code else None,
        )

    def verify_email_code(
        self,
        *,
        email: str,
        code: str,
        session_id: str | None,
        actor: ActorContext,
        response: Response,
    ) -> UserAccount:
        normalized = email.strip().lower()
        state = self.store.load()
        verification = state.verifications.get(normalized)
        if verification is None:
            raise ValueError("No email verification is pending for this address.")
        if verification.used_at is not None:
            raise ValueError("This verification code was already used.")
        if verification.expires_at < utc_now():
            raise ValueError("The verification code has expired.")
        if verification.code != code.strip():
            verification.attempts += 1
            state.verifications[normalized] = verification
            self.store.save(state)
            raise ValueError("The verification code is invalid.")

        user = next(
            (item for item in state.users.values() if item.email.strip().lower() == normalized),
            None,
        )
        if user is None:
            user = UserAccount(email=normalized)
        user.email_verified_at = utc_now()
        user.updated_at = utc_now()

        if actor.guest_id:
            guest = state.guests.get(actor.guest_id)
            if guest is not None:
                guest.linked_user_id = user.user_id
                guest.last_seen_at = utc_now()
                if actor.guest_id not in user.linked_guest_ids:
                    user.linked_guest_ids.append(actor.guest_id)
                state.guests[guest.guest_id] = guest
                self.usage_service.transfer_trial_usage(
                    guest_id=guest.guest_id,
                    user_id=user.user_id,
                )

        state.users[user.user_id] = user
        verification.used_at = utc_now()
        state.verifications[normalized] = verification
        self.store.save(state)

        if session_id:
            session = self.session_store.get(session_id)
            session.user_id = user.user_id
            if session.guest_id is None and actor.guest_id is not None:
                session.guest_id = actor.guest_id
            self.session_store.save(session)

        self._set_user_cookie(response, user.user_id)
        return user

    def assert_session_access(self, session: CounselingSession, actor: ActorContext) -> None:
        if actor.actor_type == ActorType.user and session.user_id == actor.user_id:
            return
        if actor.guest_id is not None and session.guest_id == actor.guest_id:
            return
        raise ValueError("You do not have access to this counseling session.")

    def to_user_response(self, user: UserAccount | None) -> UserResponse | None:
        if user is None:
            return None
        return UserResponse(
            user_id=user.user_id,
            email=user.email,
            email_verified_at=user.email_verified_at,
        )

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

    def _set_user_cookie(self, response: Response, user_id: str) -> None:
        response.set_cookie(
            key=self.settings.user_cookie_name,
            value=user_id,
            httponly=True,
            samesite="lax",
            secure=self.settings.cookie_secure,
            max_age=60 * 60 * 24 * 90,
            path="/",
        )
