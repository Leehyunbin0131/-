from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.chat.models import (
    FollowupResponse,
    SessionAnswerRequest,
    SessionMessageRequest,
    SessionProgressResponse,
    SessionStartRequest,
    SessionStatusResponse,
    SessionSummaryResponse,
)
from app.dependencies import ServiceContainer, get_container

router = APIRouter()


def _raise_http_error(exc: ValueError, *, not_found: bool = False) -> None:
    detail = str(exc)
    if "Upgrade required" in detail:
        raise HTTPException(status_code=402, detail=detail) from exc
    if "access" in detail.lower() or "identity" in detail.lower():
        raise HTTPException(status_code=401, detail=detail) from exc
    if not_found:
        raise HTTPException(status_code=404, detail=detail) from exc
    raise HTTPException(status_code=400, detail=detail) from exc


@router.post("/session/start", response_model=SessionProgressResponse)
def start_session(
    request: Request,
    response: Response,
    payload: SessionStartRequest,
    container: ServiceContainer = Depends(get_container),
) -> SessionProgressResponse:
    try:
        actor = container.auth_service.ensure_actor(request, response)
        progress = container.orchestrator.start_session(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            guest_id=actor.guest_id,
            user_id=actor.user_id,
        )
        container.auth_service.register_session(actor, progress.session_id)
        return progress
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/session/{session_id}/answer", response_model=SessionProgressResponse)
def answer_session_question(
    request: Request,
    session_id: str,
    payload: SessionAnswerRequest,
    container: ServiceContainer = Depends(get_container),
) -> SessionProgressResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)
        return container.orchestrator.answer_intake_question(
            session_id,
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except ValueError as exc:
        _raise_http_error(exc)


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
def get_session(
    request: Request,
    session_id: str,
    container: ServiceContainer = Depends(get_container),
) -> SessionStatusResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)
        return container.orchestrator.get_session_status(
            session_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except ValueError as exc:
        _raise_http_error(exc, not_found=True)


@router.post("/session/{session_id}/complete", response_model=SessionSummaryResponse)
def complete_session(
    request: Request,
    session_id: str,
    container: ServiceContainer = Depends(get_container),
) -> SessionSummaryResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)
        return container.orchestrator.generate_counseling_summary(
            session_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/session/{session_id}/message", response_model=FollowupResponse)
def send_followup_message(
    request: Request,
    session_id: str,
    payload: SessionMessageRequest,
    container: ServiceContainer = Depends(get_container),
) -> FollowupResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)
        return container.orchestrator.send_followup_message(
            session_id,
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except ValueError as exc:
        _raise_http_error(exc)
