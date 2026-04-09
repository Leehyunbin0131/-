from __future__ import annotations

from stripe import SignatureVerificationError, StripeClient, Webhook

from app.billing.provider_base import BillingProviderBase
from app.config import Settings


class StripeProvider(BillingProviderBase):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def client(self) -> StripeClient:
        if not self.settings.stripe_secret_key:
            raise ValueError("COUNSEL_STRIPE_SECRET_KEY is not configured.")
        return StripeClient(self.settings.stripe_secret_key)

    def create_checkout_session(
        self,
        *,
        customer_email: str,
        amount_cents: int,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
    ) -> tuple[str, str]:
        line_item: dict[str, object]
        if self.settings.stripe_price_id:
            line_item = {"price": self.settings.stripe_price_id, "quantity": 1}
        else:
            line_item = {
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": "Career Counsel 30-turn pack"},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }

        session = self.client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "customer_email": customer_email,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [line_item],
                "metadata": metadata,
            }
        )
        return str(session.id), str(session.url)

    def construct_webhook_event(self, *, payload: bytes, signature: str):
        if not self.settings.stripe_webhook_secret:
            raise ValueError("COUNSEL_STRIPE_WEBHOOK_SECRET is not configured.")
        if not signature:
            raise ValueError("Stripe-Signature header is missing.")
        try:
            return Webhook.construct_event(
                payload.decode("utf-8"),
                signature,
                self.settings.stripe_webhook_secret,
            )
        except SignatureVerificationError as exc:
            raise ValueError("Invalid Stripe webhook signature.") from exc
        except ValueError:
            raise
