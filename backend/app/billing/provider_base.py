from __future__ import annotations

from abc import ABC, abstractmethod


class BillingProviderBase(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def construct_webhook_event(self, *, payload: bytes, signature: str):
        raise NotImplementedError
