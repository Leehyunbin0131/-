from __future__ import annotations

from app.config import Settings
from app.usage.models import (
    ActorType,
    QuotaState,
    TurnType,
    UsageEvent,
)
from app.usage.store import UsageStore


class UsageService:
    def __init__(self, settings: Settings, store: UsageStore) -> None:
        self.settings = settings
        self.store = store

    def quota_for_actor(self, actor_type: ActorType, actor_id: str) -> QuotaState:
        state = self.store.load()
        actor_key = self._actor_key(actor_type, actor_id)
        used = state.usage_by_actor.get(actor_key, 0)
        remaining = max(0, self.settings.trial_turn_limit - used)

        return QuotaState(
            actor_type=actor_type,
            actor_id=actor_id,
            limit=self.settings.trial_turn_limit,
            used=used,
            remaining=remaining,
            exhausted=remaining <= 0,
            can_chat=remaining > 0,
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
        actor_key = self._actor_key(actor_type, actor_id)
        current = state.usage_by_actor.get(actor_key, 0)
        if current >= self.settings.trial_turn_limit:
            raise ValueError("Usage limit exceeded for this recommendation session.")
        state.usage_by_actor[actor_key] = current + 1

        event = UsageEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            session_id=session_id,
            request_id=request_id,
            turn_type=turn_type,
        )
        state.events.append(event)
        self.store.save(state)
        return event, self.quota_for_actor(actor_type, actor_id)

    def _actor_key(self, actor_type: ActorType, actor_id: str) -> str:
        return f"{actor_type.value}:{actor_id}"
