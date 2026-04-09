from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorType(str, Enum):
    guest = "guest"


class TurnType(str, Enum):
    summary = "summary"
    followup = "followup"


class UsageEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    actor_type: ActorType = ActorType.guest
    actor_id: str
    session_id: str
    request_id: str
    turn_type: TurnType
    created_at: datetime = Field(default_factory=utc_now)


class QuotaState(BaseModel):
    actor_type: ActorType = ActorType.guest
    actor_id: str
    limit: int
    used: int
    remaining: int
    exhausted: bool
    can_chat: bool


class UsageState(BaseModel):
    usage_by_actor: dict[str, int] = Field(default_factory=dict)
    events: list[UsageEvent] = Field(default_factory=list)
