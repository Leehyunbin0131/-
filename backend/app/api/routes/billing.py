from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.billing.models import CheckoutCreateRequest, CheckoutCreateResponse
from app.dependencies import ServiceContainer, get_container
from app.usage.models import ActorType, QuotaState

router = APIRouter()


@router.get("/entitlement", response_model=QuotaState)
def get_entitlement_state(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> QuotaState:
    try:
        actor = container.auth_service.require_actor(request)
        return container.usage_service.quota_for_actor(actor.actor_type, actor.actor_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 401 if "identity" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/checkout", response_model=CheckoutCreateResponse)
def create_checkout(
    request: Request,
    payload: CheckoutCreateRequest,
    container: ServiceContainer = Depends(get_container),
) -> CheckoutCreateResponse:
    try:
        actor = container.auth_service.require_actor(request)
        if actor.actor_type != ActorType.user or actor.user_id is None:
            raise ValueError("A verified user account is required before checkout.")
        if payload.session_id:
            session = container.session_store.get(payload.session_id)
            container.auth_service.assert_session_access(session, actor)
        return container.billing_service.create_checkout(
            user_id=actor.user_id,
            session_id=payload.session_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 401 if "required before checkout" in detail.lower() or "access" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
