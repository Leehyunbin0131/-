from __future__ import annotations

from app.auth.store import AuthStore
from app.billing.models import (
    CheckoutCreateResponse,
    CheckoutOrder,
    CheckoutOrderStatus,
    PaymentRecord,
    PaymentStatus,
    WebhookEvent,
    utc_now,
)
from app.billing.provider_base import BillingProviderBase
from app.billing.store import BillingStore
from app.config import Settings
from app.usage.service import UsageService


class BillingService:
    def __init__(
        self,
        settings: Settings,
        store: BillingStore,
        auth_store: AuthStore,
        usage_service: UsageService,
        provider: BillingProviderBase,
    ) -> None:
        self.settings = settings
        self.store = store
        self.auth_store = auth_store
        self.usage_service = usage_service
        self.provider = provider

    def create_checkout(self, *, user_id: str, session_id: str | None = None) -> CheckoutCreateResponse:
        user = self.auth_store.get_user(user_id)
        if user is None or user.email_verified_at is None:
            raise ValueError("A verified email account is required before checkout.")

        order = CheckoutOrder(
            user_id=user_id,
            session_id=session_id,
            amount_cents=self.settings.paid_pack_price_cents,
            currency=self.settings.paid_pack_currency,
            turns=self.settings.paid_turn_pack_size,
        )
        checkout_session_id, checkout_url = self.provider.create_checkout_session(
            customer_email=user.email,
            amount_cents=order.amount_cents,
            currency=order.currency,
            success_url=self._success_url(order.order_id),
            cancel_url=self._cancel_url(order.order_id),
            metadata={
                "order_id": order.order_id,
                "user_id": user_id,
                "session_id": session_id or "",
                "turns": str(order.turns),
            },
        )
        order.checkout_session_id = checkout_session_id
        order.checkout_url = checkout_url
        order.status = CheckoutOrderStatus.open
        order.updated_at = utc_now()

        state = self.store.load()
        state.orders[order.order_id] = order
        self.store.save(state)
        return CheckoutCreateResponse(checkout_url=checkout_url, order_id=order.order_id)

    def process_webhook(self, *, payload: bytes, signature: str) -> str:
        event = self.provider.construct_webhook_event(payload=payload, signature=signature)
        event_id = str(self._event_value(event, "id"))
        event_type = str(self._event_value(event, "type"))

        state = self.store.load()
        if event_id in state.processed_events:
            return event_type

        if event_type == "checkout.session.completed":
            checkout_session = self._event_value(self._event_value(event, "data"), "object")
            metadata = self._event_value(checkout_session, "metadata") or {}
            order_id = str(metadata.get("order_id") or "")
            order = state.orders.get(order_id)
            if order is not None:
                order.status = CheckoutOrderStatus.paid
                order.paid_at = utc_now()
                order.updated_at = utc_now()
                order.checkout_session_id = str(self._event_value(checkout_session, "id") or order.checkout_session_id)
                if not self.usage_service.has_entitlement_for_order(order.order_id):
                    payment = PaymentRecord(
                        order_id=order.order_id,
                        user_id=order.user_id,
                        provider="stripe",
                        provider_session_id=order.checkout_session_id or "",
                        amount_cents=order.amount_cents,
                        currency=order.currency,
                        status=PaymentStatus.paid,
                    )
                    state.payments[payment.payment_id] = payment
                    self.usage_service.grant_entitlement(
                        user_id=order.user_id,
                        turns_total=order.turns,
                        checkout_session_id=order.checkout_session_id,
                        payment_id=payment.payment_id,
                        source_order_id=order.order_id,
                    )
                state.orders[order.order_id] = order

        if event_type == "checkout.session.expired":
            checkout_session = self._event_value(self._event_value(event, "data"), "object")
            metadata = self._event_value(checkout_session, "metadata") or {}
            order_id = str(metadata.get("order_id") or "")
            order = state.orders.get(order_id)
            if order is not None:
                order.status = CheckoutOrderStatus.expired
                order.updated_at = utc_now()
                state.orders[order.order_id] = order

        state.processed_events[event_id] = WebhookEvent(event_id=event_id, event_type=event_type)
        self.store.save(state)
        return event_type

    def _success_url(self, order_id: str) -> str:
        return f"{self.settings.frontend_app_url}/checkout/success?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}"

    def _cancel_url(self, order_id: str) -> str:
        return f"{self.settings.frontend_app_url}/checkout/cancel?order_id={order_id}"

    def _event_value(self, obj, key: str):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)
