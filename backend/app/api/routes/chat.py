from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.chat.models import (
    CompleteSessionAcceptedResponse,
    CounselingStage,
    FollowupAcceptedResponse,
    FollowupResponse,
    SessionAnswerRequest,
    SessionMessageRequest,
    SessionProgressResponse,
    SessionStartRequest,
    SessionStatusResponse,
    SessionSummaryResponse,
    SummaryJobStatus,
)
from app.chat.followup_job import run_followup_message_job
from app.chat.summary_job import run_counseling_summary_job
from app.dependencies import ServiceContainer, get_container
from app.usage.models import ActorType

router = APIRouter()
SUMMARY_RUNNING_MESSAGE = "추천 요약을 생성 중입니다. 자료량에 따라 약 5분 정도 소요될 수 있습니다."
SUMMARY_STARTED_MESSAGE = (
    "추천 요약 생성을 시작했습니다. 자료량과 파일 수에 따라 약 5분 정도 소요될 수 있습니다."
)
FOLLOWUP_RUNNING_MESSAGE = (
    "후속 답변을 생성 중입니다. 자료량에 따라 약 5분 정도 소요될 수 있습니다."
)
FOLLOWUP_STARTED_MESSAGE = (
    "후속 답변 생성을 시작했습니다. 자료량에 따라 약 5분 정도 소요될 수 있습니다."
)


def _raise_http_error(exc: ValueError, *, not_found: bool = False) -> None:
    detail = str(exc)
    if "Usage limit exceeded" in detail:
        raise HTTPException(status_code=429, detail=detail) from exc
    if "access" in detail.lower() or "identity" in detail.lower():
        raise HTTPException(status_code=401, detail=detail) from exc
    if not_found:
        raise HTTPException(status_code=404, detail=detail) from exc
    raise HTTPException(status_code=400, detail=detail) from exc


def _accepted_summary_response(session_id: str, message: str) -> JSONResponse:
    payload = CompleteSessionAcceptedResponse(
        session_id=session_id,
        summary_job_status=SummaryJobStatus.running,
        message=message,
    )
    return JSONResponse(status_code=202, content=payload.model_dump(mode="json"))


def _accepted_followup_response(session_id: str, client_request_id: str, message: str) -> JSONResponse:
    payload = FollowupAcceptedResponse(
        session_id=session_id,
        client_request_id=client_request_id,
        followup_job_status=SummaryJobStatus.running,
        message=message,
    )
    return JSONResponse(status_code=202, content=payload.model_dump(mode="json"))


def _enqueue_summary_job(
    *,
    session_id: str,
    actor_type: ActorType,
    actor_id: str,
    container: ServiceContainer,
    background_tasks: BackgroundTasks,
) -> None:
    session = container.session_store.get(session_id)
    session.summary_job_status = SummaryJobStatus.running
    session.summary_job_error = None
    container.session_store.save(session)
    background_tasks.add_task(
        run_counseling_summary_job,
        container,
        session_id,
        actor_type=actor_type,
        actor_id=actor_id,
    )


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


@router.post("/session/{session_id}/complete", response_model=None)
def complete_session(
    request: Request,
    session_id: str,
    background_tasks: BackgroundTasks,
    container: ServiceContainer = Depends(get_container),
) -> SessionSummaryResponse | JSONResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)

        if session.final_summary is not None:
            return container.orchestrator.generate_counseling_summary(
                session_id,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )

        if session.stage == CounselingStage.intake:
            raise ValueError("Intake is not complete yet.")

        quota = container.usage_service.quota_for_actor(actor.actor_type, actor.actor_id)
        if not quota.can_chat:
            raise ValueError("Usage limit exceeded for this recommendation session.")

        if session.summary_job_status == SummaryJobStatus.running:
            return _accepted_summary_response(session_id, SUMMARY_RUNNING_MESSAGE)

        if session.summary_job_status == SummaryJobStatus.failed:
            session.summary_job_status = SummaryJobStatus.none
            session.summary_job_error = None
            container.session_store.save(session)

        _enqueue_summary_job(
            session_id=session_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            container=container,
            background_tasks=background_tasks,
        )
        return _accepted_summary_response(session_id, SUMMARY_STARTED_MESSAGE)
    except ValueError as exc:
        _raise_http_error(exc)


@router.post("/session/{session_id}/message", response_model=None)
def send_followup_message(
    request: Request,
    session_id: str,
    payload: SessionMessageRequest,
    background_tasks: BackgroundTasks,
    container: ServiceContainer = Depends(get_container),
) -> FollowupResponse | JSONResponse:
    try:
        actor = container.auth_service.require_actor(request)
        session = container.session_store.get(session_id)
        container.auth_service.assert_session_access(session, actor)

        if not payload.question.strip():
            raise ValueError("Question must not be empty.")

        cached = container.orchestrator.followup_response_if_cached(
            session_id,
            payload.client_request_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        if cached is not None:
            return cached

        if session.final_summary is None:
            raise ValueError("Generate the recommendation summary before follow-up questions.")

        if session.summary_job_status == SummaryJobStatus.running:
            raise ValueError("추천 요약을 아직 생성 중입니다. 완료된 뒤 다시 시도해 주세요.")

        quota = container.usage_service.quota_for_actor(actor.actor_type, actor.actor_id)
        if not quota.can_chat:
            raise ValueError("Usage limit exceeded for this recommendation session.")

        if session.followup_job_status == SummaryJobStatus.running:
            if session.followup_pending_client_request_id != payload.client_request_id:
                raise ValueError("다른 후속 질문을 처리하는 중입니다. 잠시만 기다려 주세요.")
            return _accepted_followup_response(
                session_id,
                payload.client_request_id,
                FOLLOWUP_RUNNING_MESSAGE,
            )

        if session.followup_job_status == SummaryJobStatus.failed:
            session.followup_job_status = SummaryJobStatus.none
            session.followup_job_error = None
            session.followup_pending_client_request_id = None
            container.session_store.save(session)

        session.followup_job_status = SummaryJobStatus.running
        session.followup_job_error = None
        session.followup_pending_client_request_id = payload.client_request_id
        container.session_store.save(session)

        background_tasks.add_task(
            run_followup_message_job,
            container,
            session_id,
            payload.model_dump(mode="json"),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        return _accepted_followup_response(
            session_id,
            payload.client_request_id,
            FOLLOWUP_STARTED_MESSAGE,
        )
    except ValueError as exc:
        _raise_http_error(exc)
