from __future__ import annotations

from app.config import Settings
from app.usage.models import (
    ActorType,
    Entitlement,
    EntitlementStatus,
    QuotaState,
    TurnType,
    UsageBucket,
    UsageEvent,
    utc_now,
)
from app.usage.store import UsageStore


class UsageService:
    def __init__(self, settings: Settings, store: UsageStore) -> None:
        self.settings = settings
        self.store = store

    def quota_for_actor(self, actor_type: ActorType, actor_id: str) -> QuotaState:
        state = self.store.load()
        trial_key = self._actor_key(actor_type, actor_id)
        trial_used = state.trial_usage.get(trial_key, 0)
        trial_remaining = max(0, self.settings.trial_turn_limit - trial_used)

        paid_total = 0
        paid_used = 0
        if actor_type == ActorType.user:
            entitlements = self._active_entitlements(state, actor_id)
            paid_total = sum(item.turns_total for item in entitlements)
            paid_used = sum(item.turns_used for item in entitlements)
        paid_remaining = max(0, paid_total - paid_used)
        total_remaining = paid_remaining if paid_remaining > 0 else trial_remaining

        return QuotaState(
            actor_type=actor_type,
            actor_id=actor_id,
            trial_limit=self.settings.trial_turn_limit,
            trial_used=trial_used,
            trial_remaining=trial_remaining,
            paid_total=paid_total,
            paid_used=paid_used,
            paid_remaining=paid_remaining,
            total_remaining=total_remaining,
            requires_upgrade=total_remaining <= 0,
            can_chat=total_remaining > 0,
        )

    def find_event(self, actor_type: ActorType, actor_id: str, request_id: str) -> UsageEvent | None:
        state = self.store.load()
        for event in reversed(state.events):
            if (
                event.actor_type == actor_type
                and event.actor_id == actor_id
                and event.request_id == request_id
            ):
                return event
        return None

    def consume_turn(
        self,
        *,
        actor_type: ActorType,
        actor_id: str,
        session_id: str,
        request_id: str,
        turn_type: TurnType,
    ) -> tuple[UsageEvent, QuotaState]:
        existing = self.find_event(actor_type, actor_id, request_id)
        if existing is not None:
            return existing, self.quota_for_actor(actor_type, actor_id)

        state = self.store.load()
        bucket = self._choose_bucket(state, actor_type, actor_id)
        if bucket == UsageBucket.trial:
            trial_key = self._actor_key(actor_type, actor_id)
            current = state.trial_usage.get(trial_key, 0)
            if current >= self.settings.trial_turn_limit:
                raise ValueError("Upgrade required to continue counseling.")
            state.trial_usage[trial_key] = current + 1
        else:
            entitlement = self._first_available_entitlement(state, actor_id)
            if entitlement is None:
                raise ValueError("No paid entitlement is available.")
            entitlement.turns_used += 1
            entitlement.updated_at = utc_now()
            if entitlement.turns_used >= entitlement.turns_total:
                entitlement.status = EntitlementStatus.spent
            state.entitlements[entitlement.entitlement_id] = entitlement

        event = UsageEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            session_id=session_id,
            request_id=request_id,
            bucket=bucket,
            turn_type=turn_type,
        )
        state.events.append(event)
        self.store.save(state)
        return event, self.quota_for_actor(actor_type, actor_id)

    def grant_entitlement(
        self,
        *,
        user_id: str,
        turns_total: int,
        checkout_session_id: str | None = None,
        payment_id: str | None = None,
        source_order_id: str | None = None,
    ) -> Entitlement:
        state = self.store.load()
        entitlement = Entitlement(
            user_id=user_id,
            turns_total=turns_total,
            checkout_session_id=checkout_session_id,
            payment_id=payment_id,
            source_order_id=source_order_id,
        )
        state.entitlements[entitlement.entitlement_id] = entitlement
        self.store.save(state)
        return entitlement

    def has_entitlement_for_order(self, order_id: str) -> bool:
        state = self.store.load()
        return any(item.source_order_id == order_id for item in state.entitlements.values())

    def transfer_trial_usage(self, *, guest_id: str, user_id: str) -> None:
        state = self.store.load()
        guest_key = self._actor_key(ActorType.guest, guest_id)
        user_key = self._actor_key(ActorType.user, user_id)
        guest_used = state.trial_usage.get(guest_key, 0)
        if guest_used <= 0:
            return
        state.trial_usage[user_key] = min(
            self.settings.trial_turn_limit,
            state.trial_usage.get(user_key, 0) + guest_used,
        )
        self.store.save(state)

    def _choose_bucket(self, state, actor_type: ActorType, actor_id: str) -> UsageBucket:
        if actor_type == ActorType.user and self._first_available_entitlement(state, actor_id) is not None:
            return UsageBucket.paid
        quota = self.quota_for_actor(actor_type, actor_id)
        if quota.trial_remaining > 0:
            return UsageBucket.trial
        raise ValueError("Upgrade required to continue counseling.")

    def _actor_key(self, actor_type: ActorType, actor_id: str) -> str:
        return f"{actor_type.value}:{actor_id}"

    def _active_entitlements(self, state, user_id: str) -> list[Entitlement]:
        entitlements = [
            item
            for item in state.entitlements.values()
            if item.user_id == user_id and item.status == EntitlementStatus.active
        ]
        entitlements.sort(key=lambda item: item.created_at)
        return entitlements

    def _first_available_entitlement(self, state, user_id: str) -> Entitlement | None:
        for entitlement in self._active_entitlements(state, user_id):
            if entitlement.turns_used < entitlement.turns_total:
                return entitlement
        return None
