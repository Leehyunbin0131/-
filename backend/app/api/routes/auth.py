from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth.models import (
    AuthStateResponse,
    EmailStartRequest,
    EmailStartResponse,
    EmailVerifyRequest,
    EmailVerifyResponse,
)
from app.dependencies import ServiceContainer, get_container
from app.usage.models import ActorType

router = APIRouter()


@router.get("/me", response_model=AuthStateResponse)
def get_auth_state(
    request: Request,
    response: Response,
    container: ServiceContainer = Depends(get_container),
) -> AuthStateResponse:
    try:
        actor = container.auth_service.ensure_actor(request, response)
        quota = container.usage_service.quota_for_actor(actor.actor_type, actor.actor_id)
        return AuthStateResponse(
            actor_type=actor.actor_type,
            guest_id=actor.guest_id,
            user=container.auth_service.to_user_response(actor.user),
            quota=quota,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/email/start", response_model=EmailStartResponse)
def start_email_verification(
    request: Request,
    payload: EmailStartRequest,
    container: ServiceContainer = Depends(get_container),
) -> EmailStartResponse:
    try:
        actor = container.auth_service.require_actor(request)
        if payload.session_id:
            session = container.session_store.get(payload.session_id)
            container.auth_service.assert_session_access(session, actor)
        return container.auth_service.start_email_verification(
            email=payload.email,
            session_id=payload.session_id,
            actor=actor,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 401 if "access" in detail.lower() or "identity" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post("/email/verify", response_model=EmailVerifyResponse)
def verify_email(
    request: Request,
    response: Response,
    payload: EmailVerifyRequest,
    container: ServiceContainer = Depends(get_container),
) -> EmailVerifyResponse:
    try:
        actor = container.auth_service.require_actor(request)
        if payload.session_id:
            session = container.session_store.get(payload.session_id)
            container.auth_service.assert_session_access(session, actor)
        user = container.auth_service.verify_email_code(
            email=payload.email,
            code=payload.code,
            session_id=payload.session_id,
            actor=actor,
            response=response,
        )
        quota = container.usage_service.quota_for_actor(actor_type=ActorType.user, actor_id=user.user_id)
        return EmailVerifyResponse(
            user=container.auth_service.to_user_response(user),
            quota=quota,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 401 if "access" in detail.lower() or "identity" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
