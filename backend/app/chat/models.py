from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.query.sql_runner import AggregateSpec, StructuredFilter
from app.usage.models import QuotaState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuestionIntent(str, Enum):
    information = "information"
    numeric = "numeric"
    counseling = "counseling"


class CounselingStage(str, Enum):
    intake = "intake"
    ready_for_summary = "ready_for_summary"
    active_counseling = "active_counseling"
    upgrade_required = "upgrade_required"
    completed = "completed"


class UserProfile(BaseModel):
    current_stage: str | None = None
    target_region: str | None = None
    goals: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    decision_pain: str | None = None
    notes: str | None = None


class EvidenceItem(BaseModel):
    dataset_id: str
    dataset_title: str
    table_id: str
    table_title: str
    snapshot_date: str | None = None
    source_path: str
    score: float | None = None
    excerpt: str
    query_rows: list[dict[str, Any]] = Field(default_factory=list)


class TableSelectionPlan(BaseModel):
    table_id: str
    rationale: str
    select: list[str] = Field(default_factory=list)
    filters: list[StructuredFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[AggregateSpec] = Field(default_factory=list)
    order_by: list[str] = Field(default_factory=list)
    limit: int = 5


class IntakeQuestion(BaseModel):
    question_id: str
    prompt: str
    profile_field: str
    help_text: str | None = None
    options: list[str] = Field(default_factory=list)
    allows_multiple: bool = False


class IntakeAnswer(BaseModel):
    question_id: str
    answer: str | list[str]


class RecommendationDirection(BaseModel):
    title: str
    fit_reason: str
    evidence_summary: str
    action_tip: str | None = None


class RiskTradeoff(BaseModel):
    direction_title: str
    risk: str
    reality_check: str


class CounselingSummary(BaseModel):
    situation_summary: str
    recommended_directions: list[RecommendationDirection] = Field(default_factory=list)
    risks_and_tradeoffs: list[RiskTradeoff] = Field(default_factory=list)
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
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    stage: CounselingStage = CounselingStage.intake
    opening_question: str | None = None
    guest_id: str | None = None
    user_id: str | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    answers: list[IntakeAnswer] = Field(default_factory=list)
    conversation: list[ConversationMessage] = Field(default_factory=list)
    current_question_id: str | None = None
    llm_provider: str | None = None
    top_k: int = 5
    include_sources: bool = True
    final_summary: CounselingSummary | None = None
    final_evidence: list[EvidenceItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_trace_id: str | None = None
    last_provider: str | None = None
    last_model: str | None = None


class SessionStartRequest(BaseModel):
    opening_question: str | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    llm_provider: str | None = None
    top_k: int = 5
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


class SessionSummaryResponse(BaseModel):
    session_id: str
    stage: CounselingStage
    summary: CounselingSummary
    evidence: list[EvidenceItem] = Field(default_factory=list)
    trace_id: str | None = None
    provider: str | None = None
    model: str | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)
    quota: QuotaState


class FollowupResponse(BaseModel):
    session_id: str
    stage: CounselingStage
    answer: str
    trace_id: str | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)
    quota: QuotaState
