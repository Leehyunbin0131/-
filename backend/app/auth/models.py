from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.usage.models import ActorType
from app.usage.models import QuotaState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuestIdentity(BaseModel):
    guest_id: str = Field(default_factory=lambda: uuid4().hex)
    linked_user_id: str | None = None
    session_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class UserAccount(BaseModel):
    user_id: str = Field(default_factory=lambda: uuid4().hex)
    email: str
    email_verified_at: datetime | None = None
    linked_guest_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EmailVerification(BaseModel):
    email: str
    code: str
    session_id: str | None = None
    guest_id: str | None = None
    expires_at: datetime
    attempts: int = 0
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        email: str,
        code: str,
        ttl_minutes: int,
        session_id: str | None,
        guest_id: str | None,
    ) -> "EmailVerification":
        return cls(
            email=email,
            code=code,
            session_id=session_id,
            guest_id=guest_id,
            expires_at=utc_now() + timedelta(minutes=ttl_minutes),
        )


class ActorContext(BaseModel):
    actor_type: ActorType
    actor_id: str
    guest_id: str | None = None
    user_id: str | None = None
    user: UserAccount | None = None


class AuthState(BaseModel):
    guests: dict[str, GuestIdentity] = Field(default_factory=dict)
    users: dict[str, UserAccount] = Field(default_factory=dict)
    verifications: dict[str, EmailVerification] = Field(default_factory=dict)


class EmailStartRequest(BaseModel):
    email: str
    session_id: str | None = None


class EmailStartResponse(BaseModel):
    email: str
    sent: bool = True
    verification_code: str | None = None


class EmailVerifyRequest(BaseModel):
    email: str
    code: str
    session_id: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    email_verified_at: datetime | None = None


class EmailVerifyResponse(BaseModel):
    actor_type: ActorType = ActorType.user
    user: UserResponse
    quota: QuotaState


class AuthStateResponse(BaseModel):
    actor_type: ActorType
    guest_id: str | None = None
    user: UserResponse | None = None
    quota: QuotaState
