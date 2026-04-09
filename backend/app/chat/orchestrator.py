from __future__ import annotations

import re
from typing import Any

from app.audit.answer_trace import AnswerTrace, AnswerTraceStore
from app.catalog.manifest import ManifestStore
from app.chat.intake import answered_count, apply_answer, get_next_question, get_question, total_questions
from app.chat.models import (
    CounselingSession,
    CounselingStage,
    CounselingSummary,
    ConversationMessage,
    ConversationRole,
    EvidenceItem,
    FollowupResponse,
    IntakeAnswer,
    QuestionIntent,
    SessionAnswerRequest,
    SessionMessageRequest,
    SessionProgressResponse,
    SessionStartRequest,
    SessionStatusResponse,
    SessionSummaryResponse,
    TableSelectionPlan,
)
from app.chat.prompts import build_followup_messages, build_selection_messages, build_summary_messages
from app.chat.session_store import SessionStore
from app.config import Settings
from app.llm.factory import ProviderFactory
from app.query.sql_runner import DuckDBQueryRunner, StructuredQuery
from app.recommendation.rules import recommend_focus_areas
from app.retrieval.vector_index import SearchHit, VectorIndex
from app.usage.models import ActorType, TurnType
from app.usage.service import UsageService


class CounselingOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        manifest_store: ManifestStore,
        session_store: SessionStore,
        vector_index: VectorIndex,
        query_runner: DuckDBQueryRunner,
        provider_factory: ProviderFactory,
        trace_store: AnswerTraceStore,
        usage_service: UsageService,
    ) -> None:
        self.settings = settings
        self.manifest_store = manifest_store
        self.session_store = session_store
        self.vector_index = vector_index
        self.query_runner = query_runner
        self.provider_factory = provider_factory
        self.trace_store = trace_store
        self.usage_service = usage_service

    def start_session(
        self,
        request: SessionStartRequest,
        *,
        actor_type: ActorType,
        actor_id: str,
        guest_id: str | None = None,
        user_id: str | None = None,
    ) -> SessionProgressResponse:
        session = CounselingSession(
            opening_question=request.opening_question,
            guest_id=guest_id,
            user_id=user_id,
            user_profile=request.user_profile.model_copy(deep=True),
            llm_provider=request.llm_provider,
            top_k=request.top_k,
            include_sources=request.include_sources,
        )
        if request.opening_question:
            self._append_message(
                session,
                role=ConversationRole.user,
                kind="opening_question",
                content=request.opening_question,
            )

        next_question = get_next_question(session.user_profile, answered_question_ids=set())
        if next_question is None:
            session.stage = CounselingStage.ready_for_summary
            session.current_question_id = None
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="ready_for_summary",
                content="좋아요. 필요한 맥락은 충분히 들었어요. 이제 통계 근거를 바탕으로 방향과 리스크를 정리해드릴게요.",
            )
        else:
            session.stage = CounselingStage.intake
            session.current_question_id = next_question.question_id
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="intake_prompt",
                content=f"좋아요. 먼저 상황을 차례대로 파악해볼게요.\n\n{next_question.prompt}",
            )
        self.session_store.create(session)
        return self._build_progress_response(session, actor_type=actor_type, actor_id=actor_id)

    def answer_intake_question(
        self,
        session_id: str,
        payload: SessionAnswerRequest,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> SessionProgressResponse:
        session = self.session_store.get(session_id)
        if session.stage != CounselingStage.intake:
            raise ValueError("This session is not accepting intake answers.")
        if not self._has_meaningful_answer(payload.answer):
            raise ValueError("Answer must not be empty.")

        if session.current_question_id is None:
            next_question = get_next_question(session.user_profile, self._answered_question_ids(session))
            if next_question is None:
                session.stage = CounselingStage.ready_for_summary
                self.session_store.save(session)
                return self._build_progress_response(session, actor_type=actor_type, actor_id=actor_id)
            session.current_question_id = next_question.question_id

        question = get_question(session.current_question_id)
        answer_text = payload.answer if isinstance(payload.answer, str) else ", ".join(payload.answer)
        self._append_message(
            session,
            role=ConversationRole.user,
            kind="intake_answer",
            content=answer_text,
        )
        apply_answer(session.user_profile, question, payload.answer)
        self._replace_answer(session, IntakeAnswer(question_id=question.question_id, answer=payload.answer))

        next_question = get_next_question(session.user_profile, self._answered_question_ids(session))
        if next_question is None:
            session.stage = CounselingStage.ready_for_summary
            session.current_question_id = None
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="ready_for_summary",
                content="좋아요. 필요한 맥락은 충분히 들었어요. 이제 통계 근거를 바탕으로 방향과 리스크를 정리해드릴게요.",
            )
        else:
            session.stage = CounselingStage.intake
            session.current_question_id = next_question.question_id
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="intake_prompt",
                content=f"좋아요. 이어서 한 가지만 더 여쭤볼게요.\n\n{next_question.prompt}",
            )

        self.session_store.save(session)
        return self._build_progress_response(session, actor_type=actor_type, actor_id=actor_id)

    def get_session_status(
        self,
        session_id: str,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> SessionStatusResponse:
        session = self.session_store.get(session_id)
        current_question = get_question(session.current_question_id) if session.current_question_id else None
        return SessionStatusResponse(
            session=session,
            current_question=current_question,
            answered_count=answered_count(session.user_profile),
            total_questions=total_questions(),
            can_complete=session.stage in {CounselingStage.ready_for_summary, CounselingStage.active_counseling},
            quota=self.usage_service.quota_for_actor(actor_type, actor_id),
        )

    def generate_counseling_summary(
        self,
        session_id: str,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> SessionSummaryResponse:
        session = self.session_store.get(session_id)
        quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        if session.final_summary is not None:
            return SessionSummaryResponse(
                session_id=session.session_id,
                stage=session.stage,
                summary=session.final_summary,
                evidence=session.final_evidence if session.include_sources else [],
                trace_id=session.last_trace_id,
                provider=session.last_provider,
                model=session.last_model,
                conversation=session.conversation,
                quota=quota,
            )
        if session.stage == CounselingStage.intake:
            raise ValueError("Intake is not complete yet.")
        if not quota.can_chat:
            session.stage = CounselingStage.upgrade_required
            self.session_store.save(session)
            raise ValueError("Upgrade required to continue counseling.")

        catalog = self.manifest_store.load()
        if not catalog.tables:
            raise ValueError("No normalized datasets are available yet. Run ingestion before counseling.")

        provider = self.provider_factory.create(session.llm_provider)
        search_query = self.compose_search_query(session)
        intent = self.classify_intent(search_query)
        hits = self._retrieve_hits(search_query, session.top_k, provider)
        evidence = self._build_evidence(session, intent, search_query, hits, provider)
        guidance = recommend_focus_areas(session.user_profile)
        summary = self._generate_summary(session, evidence, guidance, provider)
        self.usage_service.consume_turn(
            actor_type=actor_type,
            actor_id=actor_id,
            session_id=session.session_id,
            request_id=f"summary:{session.session_id}",
            turn_type=TurnType.summary,
        )

        trace = self.trace_store.append(
            AnswerTrace(
                session_id=session.session_id,
                provider=provider.profile.provider,
                model=provider.profile.chat_model,
                question=search_query,
                intent="counseling_session",
                datasets=sorted({item.dataset_id for item in evidence}),
                tables=[item.table_id for item in evidence],
                filters=[],
                evidence=[item.model_dump(mode="json") for item in evidence],
                answer=self._render_summary_text(summary),
            )
        )

        post_quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        session.stage = CounselingStage.active_counseling if post_quota.can_chat else CounselingStage.upgrade_required
        session.final_summary = summary
        session.final_evidence = evidence
        session.last_trace_id = trace.trace_id
        session.last_provider = provider.profile.provider
        session.last_model = provider.profile.chat_model
        self._append_message(
            session,
            role=ConversationRole.assistant,
            kind="summary",
            content=self._render_summary_text(summary),
            request_id=f"summary:{session.session_id}",
        )
        self.session_store.save(session)

        return SessionSummaryResponse(
            session_id=session.session_id,
            stage=session.stage,
            summary=summary,
            evidence=evidence if session.include_sources else [],
            trace_id=trace.trace_id,
            provider=provider.profile.provider,
            model=provider.profile.chat_model,
            conversation=session.conversation,
            quota=post_quota,
        )

    def send_followup_message(
        self,
        session_id: str,
        payload: SessionMessageRequest,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> FollowupResponse:
        session = self.session_store.get(session_id)
        if session.final_summary is None:
            raise ValueError("Generate the counseling summary before follow-up questions.")
        if not payload.question.strip():
            raise ValueError("Question must not be empty.")

        existing = self._find_followup_response(session, payload.client_request_id)
        if existing is not None:
            return FollowupResponse(
                session_id=session.session_id,
                stage=session.stage,
                answer=existing.content,
                trace_id=session.last_trace_id,
                conversation=session.conversation,
                quota=self.usage_service.quota_for_actor(actor_type, actor_id),
            )

        quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        if not quota.can_chat:
            session.stage = CounselingStage.upgrade_required
            self.session_store.save(session)
            raise ValueError("Upgrade required to continue counseling.")

        provider = self.provider_factory.create(session.llm_provider)
        search_query = f"{self.compose_search_query(session)} | 후속 질문: {payload.question}"
        intent = self.classify_intent(payload.question)
        hits = self._retrieve_hits(search_query, session.top_k, provider)
        evidence = self._build_evidence(session, intent, search_query, hits, provider)
        answer = self._generate_followup_answer(
            session=session,
            question=payload.question,
            evidence=evidence,
            provider=provider,
        )
        self.usage_service.consume_turn(
            actor_type=actor_type,
            actor_id=actor_id,
            session_id=session.session_id,
            request_id=payload.client_request_id,
            turn_type=TurnType.followup,
        )
        trace = self.trace_store.append(
            AnswerTrace(
                session_id=session.session_id,
                provider=provider.profile.provider,
                model=provider.profile.chat_model,
                question=payload.question,
                intent="followup_counseling",
                datasets=sorted({item.dataset_id for item in evidence}),
                tables=[item.table_id for item in evidence],
                filters=[],
                evidence=[item.model_dump(mode="json") for item in evidence],
                answer=answer,
            )
        )
        self._append_message(
            session,
            role=ConversationRole.user,
            kind="followup_question",
            content=payload.question,
            request_id=payload.client_request_id,
        )
        self._append_message(
            session,
            role=ConversationRole.assistant,
            kind="followup_answer",
            content=answer,
            request_id=payload.client_request_id,
        )
        session.last_trace_id = trace.trace_id
        session.last_provider = provider.profile.provider
        session.last_model = provider.profile.chat_model
        post_quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        session.stage = CounselingStage.active_counseling if post_quota.can_chat else CounselingStage.upgrade_required
        self.session_store.save(session)
        return FollowupResponse(
            session_id=session.session_id,
            stage=session.stage,
            answer=answer,
            trace_id=trace.trace_id,
            conversation=session.conversation,
            quota=post_quota,
        )

    def compose_search_query(self, session: CounselingSession) -> str:
        parts: list[str] = []
        if session.opening_question:
            parts.append(session.opening_question)
        profile = session.user_profile
        if profile.current_stage:
            parts.append(f"현재 단계: {profile.current_stage}")
        if profile.goals:
            parts.append(f"원하는 결과: {', '.join(profile.goals)}")
        if profile.interests:
            parts.append(f"관심 분야: {', '.join(profile.interests)}")
        if profile.avoidances:
            parts.append(f"피하고 싶은 방향: {', '.join(profile.avoidances)}")
        if profile.priorities:
            parts.append(f"중요 기준: {', '.join(profile.priorities)}")
        if profile.target_region:
            parts.append(f"선호 지역: {profile.target_region}")
        if profile.constraints:
            parts.append(f"제약 조건: {', '.join(profile.constraints)}")
        if profile.decision_pain:
            parts.append(f"핵심 고민: {profile.decision_pain}")
        return " | ".join(parts) or "진학 취업 상담 통계"

    def classify_intent(self, question: str) -> QuestionIntent:
        lowered = question.lower()
        if re.search(r"\b(20\d{2}|\d+%|\d+명)\b", question) or any(
            token in lowered for token in ("rate", "ratio", "compare", "average", "employment", "admission")
        ):
            return QuestionIntent.numeric
        if any(token in question for token in ("추천", "고민", "진로", "상담", "어떻게", "어디", "취업", "진학")):
            return QuestionIntent.counseling
        return QuestionIntent.information

    def _retrieve_hits(self, question: str, top_k: int, provider: Any) -> list[SearchHit]:
        try:
            hits = self.vector_index.search(provider, question, top_k=top_k)
            if hits:
                return hits
        except Exception:
            pass
        return self._keyword_fallback(question, top_k)

    def _keyword_fallback(self, question: str, top_k: int) -> list[SearchHit]:
        catalog = self.manifest_store.load()
        tokens = {token for token in re.split(r"\W+", question.lower()) if token}
        hits: list[SearchHit] = []
        for dataset in catalog.datasets.values():
            for table in catalog.dataset_tables(dataset.dataset_id):
                columns = catalog.table_columns(table.table_id)
                text = " ".join(
                    [
                        dataset.title,
                        table.title,
                        table.sheet_name,
                        " ".join(column.name for column in columns),
                    ]
                ).lower()
                score = float(sum(1 for token in tokens if token and token in text))
                if score <= 0:
                    continue
                hits.append(
                    SearchHit(
                        doc_id=table.table_id,
                        score=score,
                        text=text,
                        metadata={
                            "dataset_id": dataset.dataset_id,
                            "dataset_title": dataset.title,
                            "table_id": table.table_id,
                            "table_title": table.title,
                            "snapshot_date": table.snapshot_date,
                            "source_path": table.source_path,
                        },
                    )
                )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def _build_evidence(
        self,
        session: CounselingSession,
        intent: QuestionIntent,
        search_query: str,
        hits: list[SearchHit],
        provider: Any,
    ) -> list[EvidenceItem]:
        if not hits:
            return []

        selection = self._plan_selection(session, intent, search_query, hits, provider)
        selected_result = self.query_runner.run_structured_query(
            StructuredQuery(
                table_id=selection.table_id,
                select=selection.select,
                filters=selection.filters,
                group_by=selection.group_by,
                aggregates=selection.aggregates,
                order_by=selection.order_by,
                limit=selection.limit,
            )
        )
        catalog = self.manifest_store.load()
        selected_table = catalog.find_table(selection.table_id)
        if selected_table is None:
            return []
        selected_metadata = next((hit.metadata for hit in hits if hit.doc_id == selection.table_id), {})
        evidence = [
            EvidenceItem(
                dataset_id=selected_metadata.get("dataset_id", selected_table.dataset_id),
                dataset_title=selected_metadata.get("dataset_title", ""),
                table_id=selected_table.table_id,
                table_title=selected_table.title,
                snapshot_date=selected_table.snapshot_date,
                source_path=selected_table.source_path,
                score=next((hit.score for hit in hits if hit.doc_id == selection.table_id), None),
                excerpt=selection.rationale,
                query_rows=selected_result.rows,
            )
        ]

        for hit in hits:
            if hit.doc_id == selection.table_id:
                continue
            table = catalog.find_table(hit.doc_id)
            if table is None:
                continue
            preview = self.query_runner.preview_table(table.table_id, limit=2)
            evidence.append(
                EvidenceItem(
                    dataset_id=hit.metadata.get("dataset_id", table.dataset_id),
                    dataset_title=hit.metadata.get("dataset_title", ""),
                    table_id=table.table_id,
                    table_title=table.title,
                    snapshot_date=table.snapshot_date,
                    source_path=table.source_path,
                    score=hit.score,
                    excerpt="보조 맥락 확인을 위한 관련 통계표 미리보기입니다.",
                    query_rows=preview.rows,
                )
            )
            if len(evidence) >= min(3, session.top_k):
                break
        return evidence

    def _plan_selection(
        self,
        session: CounselingSession,
        intent: QuestionIntent,
        search_query: str,
        hits: list[SearchHit],
        provider: Any,
    ) -> TableSelectionPlan:
        catalog = self.manifest_store.load()
        candidate_tables: list[dict[str, Any]] = []
        for hit in hits[: min(5, len(hits))]:
            table = catalog.find_table(hit.doc_id)
            if table is None:
                continue
            candidate_tables.append(
                {
                    "table_id": table.table_id,
                    "dataset_id": table.dataset_id,
                    "table_title": table.title,
                    "sheet_name": table.sheet_name,
                    "snapshot_date": table.snapshot_date,
                    "dimensions": table.dimensions,
                    "grain": table.grain,
                    "score": hit.score,
                }
            )
        if not candidate_tables:
            first_hit = hits[0]
            return TableSelectionPlan(table_id=first_hit.doc_id, rationale="Fallback to best keyword match.")

        try:
            messages = build_selection_messages(
                search_query=search_query,
                user_profile=session.user_profile,
                intent=intent,
                candidate_tables=candidate_tables,
            )
            response = provider.generate(messages, response_model=TableSelectionPlan, temperature=0.0)
            if response.parsed:
                plan = TableSelectionPlan.model_validate(response.parsed)
                valid_table_ids = {item["table_id"] for item in candidate_tables}
                if plan.table_id in valid_table_ids:
                    return plan
        except Exception:
            pass

        fallback = candidate_tables[0]
        return TableSelectionPlan(
            table_id=str(fallback["table_id"]),
            rationale="가장 관련도가 높은 통계표를 우선 근거로 선택했습니다.",
            limit=self.settings.parquet_preview_limit,
        )

    def _generate_summary(
        self,
        session: CounselingSession,
        evidence: list[EvidenceItem],
        guidance: list[str],
        provider: Any,
    ) -> CounselingSummary:
        if not evidence:
            return self._deterministic_summary_without_evidence(session)

        try:
            messages = build_summary_messages(
                session=session,
                evidence=evidence,
                guidance=guidance,
            )
            response = provider.generate(messages, response_model=CounselingSummary, temperature=0.2)
            if response.parsed:
                return CounselingSummary.model_validate(response.parsed)
        except Exception:
            pass
        return self._deterministic_summary(session, evidence, guidance)

    def _generate_followup_answer(
        self,
        *,
        session: CounselingSession,
        question: str,
        evidence: list[EvidenceItem],
        provider: Any,
    ) -> str:
        try:
            messages = build_followup_messages(session=session, question=question, evidence=evidence)
            response = provider.generate(messages, temperature=0.2)
            if response.content.strip():
                return response.content.strip()
        except Exception:
            pass
        return self._deterministic_followup_answer(session, question, evidence)

    def _deterministic_summary_without_evidence(self, session: CounselingSession) -> CounselingSummary:
        return CounselingSummary(
            situation_summary=(
                "현재 상담 내용을 바탕으로 방향을 정리하기에는 통계 근거가 아직 충분하지 않았습니다. "
                "질문을 더 좁히거나, 연도·지역·학과 같은 조건을 조금 더 구체화하면 더 정확하게 정리할 수 있어요."
            ),
            recommended_directions=[
                {
                    "title": "질문 범위를 먼저 좁히기",
                    "fit_reason": "지금은 진학과 취업 범위가 넓어서 어떤 통계를 우선 봐야 할지 모호합니다.",
                    "evidence_summary": "사용 가능한 통계표에서 직접 연결되는 근거를 충분히 찾지 못했습니다.",
                    "action_tip": "예: 서울권 IT 계열, 전문대 vs 4년제, 취업률 우선 등으로 좁혀보세요.",
                }
            ],
            risks_and_tradeoffs=[
                {
                    "direction_title": "질문 범위를 먼저 좁히기",
                    "risk": "범위가 넓으면 조언이 일반론에 머무를 수 있습니다.",
                    "reality_check": "조건을 좁힐수록 실제 의사결정에 쓸 수 있는 답으로 바뀝니다.",
                }
            ],
            next_actions=[
                "희망 지역을 정리해보세요.",
                "관심 분야 2~3개를 우선순위로 적어보세요.",
                "취업 안정성, 적성, 학비 중 무엇이 가장 중요한지 정해보세요.",
            ],
            closing_message="원하시면 다음 단계에서 조건을 더 좁혀서 다시 정리해드릴게요.",
        )

    def _deterministic_summary(
        self,
        session: CounselingSession,
        evidence: list[EvidenceItem],
        guidance: list[str],
    ) -> CounselingSummary:
        lead = evidence[0]
        profile = session.user_profile
        situation_bits: list[str] = []
        if profile.current_stage:
            situation_bits.append(f"현재 단계는 {profile.current_stage}")
        if profile.interests:
            situation_bits.append(f"관심 분야는 {', '.join(profile.interests)}")
        if profile.priorities:
            situation_bits.append(f"중요 기준은 {', '.join(profile.priorities)}")
        if profile.target_region:
            situation_bits.append(f"희망 지역은 {profile.target_region}")
        if profile.constraints:
            situation_bits.append(f"고려할 제약은 {', '.join(profile.constraints)}")

        situation_summary = " / ".join(situation_bits) if situation_bits else "현재 상황을 바탕으로 상담을 정리했습니다."
        evidence_summary = (
            f"{lead.table_title} 통계표를 우선 근거로 봤고, "
            f"{lead.snapshot_date or '최신 확인 가능 시점'} 기준 데이터를 참고했습니다."
        )
        primary_title = "취업 안정성이 높은 방향부터 먼저 좁혀보기"
        secondary_title = "관심 분야와 현실 조건이 함께 맞는 선택지 찾기"

        directions = [
            {
                "title": primary_title,
                "fit_reason": "지금 상담에서는 안정적으로 결과를 확인할 수 있는 방향부터 후보를 줄이는 편이 좋습니다.",
                "evidence_summary": evidence_summary,
                "action_tip": "먼저 지역과 분야 기준으로 후보를 3개 안쪽으로 줄여보세요.",
            },
            {
                "title": secondary_title,
                "fit_reason": "관심 분야만 따라가거나 취업률만 보는 극단적인 선택보다 두 조건을 함께 보는 편이 현실적입니다.",
                "evidence_summary": "보조 통계표도 함께 참고해 단일 수치만 보지 않도록 했습니다.",
                "action_tip": "관심 분야별로 학과·학교 유형·지역을 한 번에 비교해보세요.",
            },
        ]

        risks = [
            {
                "direction_title": primary_title,
                "risk": "취업률이 높아 보여도 본인의 흥미와 맞지 않으면 지속하기 어렵습니다.",
                "reality_check": "숫자는 시작점으로 쓰고, 실제 전공/직무 적합성은 따로 점검해야 합니다.",
            },
            {
                "direction_title": secondary_title,
                "risk": "흥미만 우선하면 지역·학비·진입 난이도 같은 현실 조건을 놓칠 수 있습니다.",
                "reality_check": "최종 선택 전에는 제약 조건과 함께 다시 걸러보는 과정이 필요합니다.",
            },
        ]

        next_actions = [
            "후보 방향을 2~3개로 줄이기",
            "각 후보의 지역·학비·취업지표를 나란히 비교하기",
            "가장 고민되는 선택지끼리만 다시 상담받기",
        ]
        if guidance:
            next_actions.append(guidance[0])

        return CounselingSummary(
            situation_summary=situation_summary,
            recommended_directions=directions,
            risks_and_tradeoffs=risks,
            next_actions=next_actions[:4],
            closing_message="정답을 단번에 고르기보다, 지금은 가능성이 높은 방향을 두세 개로 좁히는 것이 가장 현실적인 다음 단계입니다.",
        )

    def _deterministic_followup_answer(
        self,
        session: CounselingSession,
        question: str,
        evidence: list[EvidenceItem],
    ) -> str:
        summary_line = (
            session.final_summary.situation_summary
            if session.final_summary is not None
            else "현재까지 정리된 상담 내용"
        )
        if evidence:
            lead = evidence[0]
            return (
                f"지금 질문은 '{question}' 이군요.\n\n"
                f"현재까지 정리된 핵심은 {summary_line} 입니다. "
                f"추가로는 {lead.table_title} 통계를 다시 참고하면 방향을 더 좁히는 데 도움이 됩니다. "
                "다만 단일 수치만으로 결론을 내리기보다, 지역·전공·현실 제약을 함께 비교해보는 것이 안전합니다."
            )
        return (
            f"지금 질문은 '{question}' 이군요.\n\n"
            f"현재까지 정리된 핵심은 {summary_line} 입니다. "
            "후속 질문을 더 정확하게 다루려면 지역, 전공, 학교 유형, 취업 안정성처럼 비교 기준을 하나 더 좁혀보세요."
        )

    def _build_progress_response(
        self,
        session: CounselingSession,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> SessionProgressResponse:
        current_question = get_question(session.current_question_id) if session.current_question_id else None
        answered = answered_count(session.user_profile)
        total = total_questions()
        latest_assistant = next(
            (item for item in reversed(session.conversation) if item.role == ConversationRole.assistant),
            None,
        )
        counselor_message = latest_assistant.content if latest_assistant else "상담을 시작해볼게요."
        return SessionProgressResponse(
            session_id=session.session_id,
            stage=session.stage,
            counselor_message=counselor_message,
            current_question=current_question,
            answered_count=answered,
            total_questions=total,
            user_profile=session.user_profile,
            can_complete=session.stage in {CounselingStage.ready_for_summary, CounselingStage.active_counseling},
            conversation=session.conversation,
            quota=self.usage_service.quota_for_actor(actor_type, actor_id),
        )

    def _answered_question_ids(self, session: CounselingSession) -> set[str]:
        return {answer.question_id for answer in session.answers}

    def _replace_answer(self, session: CounselingSession, answer: IntakeAnswer) -> None:
        remaining = [item for item in session.answers if item.question_id != answer.question_id]
        remaining.append(answer)
        session.answers = remaining

    def _has_meaningful_answer(self, answer: str | list[str]) -> bool:
        if isinstance(answer, list):
            return any(item.strip() for item in answer)
        return bool(answer.strip())

    def _append_message(
        self,
        session: CounselingSession,
        *,
        role: ConversationRole,
        kind: str,
        content: str,
        request_id: str | None = None,
    ) -> None:
        session.conversation.append(
            ConversationMessage(
                role=role,
                kind=kind,
                content=content,
                request_id=request_id,
            )
        )

    def _find_followup_response(
        self,
        session: CounselingSession,
        request_id: str,
    ) -> ConversationMessage | None:
        for message in session.conversation:
            if (
                message.role == ConversationRole.assistant
                and message.kind == "followup_answer"
                and message.request_id == request_id
            ):
                return message
        return None

    def _render_summary_text(self, summary: CounselingSummary) -> str:
        direction_titles = ", ".join(item.title for item in summary.recommended_directions)
        risk_titles = ", ".join(item.direction_title for item in summary.risks_and_tradeoffs)
        return (
            f"상황 요약: {summary.situation_summary}\n"
            f"추천 방향: {direction_titles}\n"
            f"리스크: {risk_titles}\n"
            f"마무리: {summary.closing_message}"
        )
