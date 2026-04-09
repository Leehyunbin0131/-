from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CheckoutOrderStatus(str, Enum):
    created = "created"
    open = "open"
    paid = "paid"
    canceled = "canceled"
    expired = "expired"


class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class CheckoutOrder(BaseModel):
    order_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    session_id: str | None = None
    amount_cents: int
    currency: str
    turns: int
    status: CheckoutOrderStatus = CheckoutOrderStatus.created
    checkout_session_id: str | None = None
    checkout_url: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    paid_at: datetime | None = None


class PaymentRecord(BaseModel):
    payment_id: str = Field(default_factory=lambda: uuid4().hex)
    order_id: str
    user_id: str
    provider: str
    provider_session_id: str
    amount_cents: int
    currency: str
    status: PaymentStatus = PaymentStatus.pending
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WebhookEvent(BaseModel):
    event_id: str
    event_type: str
    processed_at: datetime = Field(default_factory=utc_now)


class BillingState(BaseModel):
    orders: dict[str, CheckoutOrder] = Field(default_factory=dict)
    payments: dict[str, PaymentRecord] = Field(default_factory=dict)
    processed_events: dict[str, WebhookEvent] = Field(default_factory=dict)


class CheckoutCreateRequest(BaseModel):
    session_id: str | None = None


class CheckoutCreateResponse(BaseModel):
    checkout_url: str
    order_id: str
