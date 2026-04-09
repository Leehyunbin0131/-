from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.usage.models import QuotaState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CounselingStage(str, Enum):
    intake = "intake"
    ready_for_summary = "ready_for_summary"
    active_counseling = "active_counseling"
    completed = "completed"


class SummaryJobStatus(str, Enum):
    """Background /complete job. none = idle or finished successfully."""

    none = "none"
    running = "running"
    failed = "failed"


class UserProfile(BaseModel):
    student_status: str | None = None
    interest_fields: list[str] = Field(default_factory=list)
    student_record_grade: str | None = None
    mock_exam_score: str | None = None
    converted_score: str | None = None
    admission_plan: str | None = None
    track_preferences: list[str] = Field(default_factory=list)
    target_region: str | None = None
    residence_preference: str | None = None
    constraints: list[str] = Field(default_factory=list)
    blocked_tracks: list[str] = Field(default_factory=list)
    notes: str | None = None


class EvidenceItem(BaseModel):
    dataset_id: str | None = None
    dataset_title: str | None = None
    school_name: str | None = None
    region: str | None = None
    snapshot_date: str | None = None
    source_path: str
    excerpt: str
    query_rows: list[dict[str, Any]] = Field(default_factory=list)


class RecommendationOption(BaseModel):
    university: str
    major: str
    track: str
    campus_or_region: str | None = None
    fit_reason: str
    evidence_summary: str
    dorm_note: str | None = None
    tuition_note: str | None = None
    next_step: str | None = None
    # 첨부 모집결과 표에서 인용한 수치·연도·근거 파일 (LLM이 채움)
    metrics_line: str | None = None
    source_file_hint: str | None = None


class IntakeQuestion(BaseModel):
    question_id: str
    prompt: str
    profile_field: str
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)
    allows_multiple: bool = False
    input_type: str = "text"
    placeholder: str | None = None


class IntakeAnswer(BaseModel):
    question_id: str
    answer: str | list[str]


class CounselingSummary(BaseModel):
    overview: str
    recommended_options: list[RecommendationOption] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    closing_message: str


class ConversationRole(str, Enum):
    assistant = "assistant"
    user = "user"


class ConversationMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid4().hex)
    role: ConversationRole
    kind: str
    content: str
    request_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CounselingSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    stage: CounselingStage = CounselingStage.intake
    opening_question: str | None = None
    guest_id: str | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    answers: list[IntakeAnswer] = Field(default_factory=list)
    conversation: list[ConversationMessage] = Field(default_factory=list)
    current_question_id: str | None = None
    include_sources: bool = True
    final_summary: CounselingSummary | None = None
    final_evidence: list[EvidenceItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_trace_id: str | None = None
    last_provider: str | None = None
    last_model: str | None = None
    last_grounding_mode: str | None = None
    last_used_web_search: bool = False
    last_used_file_input: bool = False
    last_file_ids: list[str] = Field(default_factory=list)
    last_file_count: int = 0
    last_region_filter: str | None = None
    summary_job_status: SummaryJobStatus = SummaryJobStatus.none
    summary_job_error: str | None = None
    followup_job_status: SummaryJobStatus = SummaryJobStatus.none
    followup_job_error: str | None = None
    followup_pending_client_request_id: str | None = None


class SessionStartRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opening_question: str | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    include_sources: bool = True


class SessionAnswerRequest(BaseModel):
    answer: str | list[str]


class SessionMessageRequest(BaseModel):
    question: str
    client_request_id: str


class SessionProgressResponse(BaseModel):
    session_id: str
    stage: CounselingStage
    counselor_message: str
    current_question: IntakeQuestion | None = None
    answered_count: int
    total_questions: int
    user_profile: UserProfile
    can_complete: bool = False
    conversation: list[ConversationMessage] = Field(default_factory=list)
    quota: QuotaState


class SessionStatusResponse(BaseModel):
    session: CounselingSession
    current_question: IntakeQuestion | None = None
    answered_count: int
    total_questions: int
    can_complete: bool = False
    quota: QuotaState


class CompleteSessionAcceptedResponse(BaseModel):
    """Returned with HTTP 202 when summary generation runs in the background."""

    session_id: str
    summary_job_status: SummaryJobStatus
    message: str


class FollowupAcceptedResponse(BaseModel):
    """Returned with HTTP 202 when a follow-up answer is generated in the background."""

    session_id: str
    client_request_id: str
    followup_job_status: SummaryJobStatus
    message: str


class SessionSummaryResponse(BaseModel):
    session_id: str
    stage: CounselingStage
    summary: CounselingSummary
    evidence: list[EvidenceItem] = Field(default_factory=list)
    trace_id: str | None = None
    provider: str | None = None
    model: str | None = None
    grounding_mode: str | None = None
    used_web_search: bool = False
    used_file_input: bool = False
    file_ids: list[str] = Field(default_factory=list)
    file_count: int = 0
    region_filter: str | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)
    quota: QuotaState


class FollowupResponse(BaseModel):
    session_id: str
    stage: CounselingStage
    answer: str
    trace_id: str | None = None
    grounding_mode: str | None = None
    used_web_search: bool = False
    used_file_input: bool = False
    file_ids: list[str] = Field(default_factory=list)
    file_count: int = 0
    region_filter: str | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)
    quota: QuotaState
