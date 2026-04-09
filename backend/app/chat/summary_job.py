from __future__ import annotations

import logging

from app.chat.models import SummaryJobStatus
from app.dependencies import ServiceContainer
from app.usage.models import ActorType

logger = logging.getLogger(__name__)


def _persist_summary_job_state(
    container: ServiceContainer,
    session_id: str,
    *,
    status: SummaryJobStatus,
    error: str | None = None,
) -> None:
    session = container.session_store.get(session_id)
    session.summary_job_status = status
    session.summary_job_error = error
    container.session_store.save(session)


def run_counseling_summary_job(
    container: ServiceContainer,
    session_id: str,
    *,
    actor_type: ActorType,
    actor_id: str,
) -> None:
    """Runs after HTTP response; updates session on success/failure."""
    orchestrator = container.orchestrator
    try:
        orchestrator.generate_counseling_summary(
            session_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    except Exception as exc:
        logger.exception("Counseling summary job failed for session %s", session_id)
        try:
            _persist_summary_job_state(
                container,
                session_id,
                status=SummaryJobStatus.failed,
                error=str(exc)[:2000],
            )
        except Exception:
            logger.exception("Could not persist summary job failure for session %s", session_id)
    else:
        try:
            _persist_summary_job_state(
                container,
                session_id,
                status=SummaryJobStatus.none,
            )
        except Exception:
            logger.exception("Could not clear summary job status for session %s", session_id)
