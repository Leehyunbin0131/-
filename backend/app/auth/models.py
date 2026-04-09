from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.usage.models import ActorType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuestIdentity(BaseModel):
    guest_id: str = Field(default_factory=lambda: uuid4().hex)
    session_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class ActorContext(BaseModel):
    actor_type: ActorType = ActorType.guest
    actor_id: str
    guest_id: str


class AuthState(BaseModel):
    guests: dict[str, GuestIdentity] = Field(default_factory=dict)
