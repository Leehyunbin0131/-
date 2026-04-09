from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorType(str, Enum):
    guest = "guest"
    user = "user"


class UsageBucket(str, Enum):
    trial = "trial"
    paid = "paid"


class TurnType(str, Enum):
    summary = "summary"
    followup = "followup"


class EntitlementStatus(str, Enum):
    active = "active"
    spent = "spent"
    revoked = "revoked"


class UsageEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    actor_type: ActorType
    actor_id: str
    session_id: str
    request_id: str
    bucket: UsageBucket
    turn_type: TurnType
    created_at: datetime = Field(default_factory=utc_now)


class Entitlement(BaseModel):
    entitlement_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    product_key: str = "one_time_30"
    turns_total: int
    turns_used: int = 0
    status: EntitlementStatus = EntitlementStatus.active
    checkout_session_id: str | None = None
    payment_id: str | None = None
    source_order_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class QuotaState(BaseModel):
    actor_type: ActorType
    actor_id: str
    trial_limit: int
    trial_used: int
    trial_remaining: int
    paid_total: int
    paid_used: int
    paid_remaining: int
    total_remaining: int
    requires_upgrade: bool
    can_chat: bool


class UsageState(BaseModel):
    trial_usage: dict[str, int] = Field(default_factory=dict)
    entitlements: dict[str, Entitlement] = Field(default_factory=dict)
    events: list[UsageEvent] = Field(default_factory=list)
