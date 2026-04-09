from __future__ import annotations

from app.auth.models import UserAccount, utc_now as auth_utc_now
from app.billing.service import BillingService
from app.billing.store import BillingStore
from app.usage.models import ActorType


class FakeBillingProvider:
    def __init__(self) -> None:
        self.last_metadata: dict[str, str] | None = None

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
        self.last_metadata = metadata
        return "cs_test_fake", "https://stripe.test/checkout"

    def construct_webhook_event(self, *, payload: bytes, signature: str):
        assert signature == "signed"
        assert self.last_metadata is not None
        return {
            "id": "evt_test_checkout_complete",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_fake",
                    "metadata": self.last_metadata,
                }
            },
        }


def test_billing_webhook_grants_turn_pack(container) -> None:
    provider = FakeBillingProvider()
    service = BillingService(
        container.settings,
        BillingStore(container.settings.billing_state_path),
        container.auth_store,
        container.usage_service,
        provider,
    )

    user = UserAccount(email="paid-user@example.com", email_verified_at=auth_utc_now())
    auth_state = container.auth_store.load()
    auth_state.users[user.user_id] = user
    container.auth_store.save(auth_state)

    checkout = service.create_checkout(user_id=user.user_id, session_id=None)
    assert checkout.checkout_url

    event_type = service.process_webhook(payload=b"{}", signature="signed")
    assert event_type == "checkout.session.completed"

    quota = container.usage_service.quota_for_actor(ActorType.user, user.user_id)
    assert quota.paid_total == container.settings.paid_turn_pack_size
    assert quota.paid_remaining == container.settings.paid_turn_pack_size
