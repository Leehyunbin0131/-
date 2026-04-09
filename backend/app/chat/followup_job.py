from __future__ import annotations

import logging
from typing import Any

from app.chat.models import SessionMessageRequest, SummaryJobStatus
from app.dependencies import ServiceContainer
from app.usage.models import ActorType

logger = logging.getLogger(__name__)


def _persist_followup_job_state(
    container: ServiceContainer,
    session_id: str,
    *,
    status: SummaryJobStatus,
    error: str | None = None,
    pending_client_request_id: str | None = None,
) -> None:
    session = container.session_store.get(session_id)
    session.followup_job_status = status
    session.followup_job_error = error
    session.followup_pending_client_request_id = pending_client_request_id
    container.session_store.save(session)


def run_followup_message_job(
    container: ServiceContainer,
    session_id: str,
    payload_body: dict[str, Any],
    *,
    actor_type: ActorType,
    actor_id: str,
) -> None:
    payload = SessionMessageRequest.model_validate(payload_body)
    try:
        container.orchestrator.send_followup_message(
            session_id,
            payload,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    except Exception as exc:
        logger.exception("Follow-up message job failed for session %s", session_id)
        try:
            _persist_followup_job_state(
                container,
                session_id,
                status=SummaryJobStatus.failed,
                error=str(exc)[:2000],
                pending_client_request_id=None,
            )
        except Exception:
            logger.exception("Could not persist follow-up job failure for session %s", session_id)
    else:
        try:
            _persist_followup_job_state(
                container,
                session_id,
                status=SummaryJobStatus.none,
                error=None,
                pending_client_request_id=None,
            )
        except Exception:
            logger.exception("Could not clear follow-up job status for session %s", session_id)
