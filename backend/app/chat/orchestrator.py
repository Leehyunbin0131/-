from __future__ import annotations

import logging
from itertools import islice
from pathlib import Path
from typing import Iterable

from app.audit.answer_trace import AnswerTrace, AnswerTraceStore
from app.catalog.manifest import ManifestStore
from app.chat.admissions_files import AdmissionsFileCandidate, filter_admissions_files, list_admissions_files
from app.chat.catalog_ranking import rank_and_cap_admissions_candidates
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
    RecommendationOption,
    SessionAnswerRequest,
    SessionMessageRequest,
    SessionProgressResponse,
    SessionStartRequest,
    SessionStatusResponse,
    SessionSummaryResponse,
)
from app.chat.prompts import (
    build_batch_synthesis_messages,
    build_followup_messages,
    build_summary_messages,
)
from app.chat.session_store import SessionStore
from app.chat.summary_recovery import counseling_summary_from_parsed_or_text
from app.config import Settings
from app.llm.factory import ProviderFactory
from app.llm.ollama_util import ollama_base_url_for_settings
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.usage.models import ActorType, TurnType
from app.usage.service import UsageService

logger = logging.getLogger(__name__)

_LIVING_INFO_TERMS = (
    "기숙사",
    "학생생활관",
    "등록금",
    "장학",
    "통학",
    "캠퍼스",
    "생활관",
)


def _chunked(values: list[AdmissionsFileCandidate], size: int) -> Iterable[list[AdmissionsFileCandidate]]:
    iterator = iter(values)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            return
        yield batch


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        ordered.append(stripped)
    return ordered


def looks_like_living_info_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return any(term in stripped for term in _LIVING_INFO_TERMS)


class CounselingOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        manifest_store: ManifestStore,
        session_store: SessionStore,
        provider_factory: ProviderFactory,
        trace_store: AnswerTraceStore,
        usage_service: UsageService,
    ) -> None:
        self.settings = settings
        self.manifest_store = manifest_store
        self.session_store = session_store
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
    ) -> SessionProgressResponse:
        session = CounselingSession(
            opening_question=request.opening_question,
            guest_id=guest_id,
            user_profile=request.user_profile.model_copy(deep=True),
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
                content="입력은 충분합니다. 이제 실제 모집결과를 기준으로 추천 후보를 정리해볼게요.",
            )
        else:
            session.stage = CounselingStage.intake
            session.current_question_id = next_question.question_id
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="intake_prompt",
                content=f"추천 정확도를 높이기 위해 이것만 먼저 볼게요.\n\n{next_question.prompt}",
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
                content="좋아요. 이제 실제 모집결과 파일과 생활 정보까지 같이 보고 추천안을 만들겠습니다.",
            )
        else:
            session.stage = CounselingStage.intake
            session.current_question_id = next_question.question_id
            self._append_message(
                session,
                role=ConversationRole.assistant,
                kind="intake_prompt",
                content=f"좋습니다. 이어서 이 정보도 알려주세요.\n\n{next_question.prompt}",
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
        region_filter = self._region_filter(session)
        if session.final_summary is not None:
            return SessionSummaryResponse(
                session_id=session.session_id,
                stage=session.stage,
                summary=session.final_summary,
                evidence=session.final_evidence if session.include_sources else [],
                trace_id=session.last_trace_id,
                provider=session.last_provider,
                model=session.last_model,
                grounding_mode=session.last_grounding_mode,
                used_web_search=session.last_used_web_search,
                used_file_input=session.last_used_file_input,
                file_ids=session.last_file_ids,
                file_count=session.last_file_count,
                region_filter=session.last_region_filter or region_filter,
                conversation=session.conversation,
                quota=quota,
            )
        if session.stage == CounselingStage.intake:
            raise ValueError("Intake is not complete yet.")
        if not quota.can_chat:
            raise ValueError("Usage limit exceeded for this recommendation session.")

        provider = self.provider_factory.create()
        file_candidates = self._select_file_candidates(session, question=None)
        if not file_candidates:
            summary = self._missing_file_summary(session)
            trace = self.trace_store.append(
                AnswerTrace(
                    session_id=session.session_id,
                    provider=provider.profile.provider,
                    model=self._model_for_trace(provider, used_web_search=False),
                    question=self._profile_brief(session),
                    intent="admissions_recommendation_summary",
                    datasets=[],
                    tables=[],
                    filters=[{"region_filter": region_filter}],
                    evidence=[],
                    grounding_mode="no_admissions_files_available",
                    used_web_search=False,
                    used_file_input=False,
                    file_ids=[],
                    file_count=0,
                    region_filter=region_filter,
                    recommended_tracks=self._recommended_tracks(summary),
                    answer=self._render_summary_text(summary),
                )
            )
            post_quota = self.usage_service.quota_for_actor(actor_type, actor_id)
            session.stage = CounselingStage.active_counseling if post_quota.can_chat else CounselingStage.completed
            session.final_summary = summary
            session.final_evidence = []
            session.last_trace_id = trace.trace_id
            session.last_provider = provider.profile.provider
            session.last_model = self._model_for_trace(provider, used_web_search=False)
            session.last_grounding_mode = "no_admissions_files_available"
            session.last_used_web_search = False
            session.last_used_file_input = False
            session.last_file_ids = []
            session.last_file_count = 0
            session.last_region_filter = region_filter
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
                evidence=[],
                trace_id=trace.trace_id,
                provider=provider.profile.provider,
                model=session.last_model,
                grounding_mode="no_admissions_files_available",
                used_web_search=False,
                used_file_input=False,
                file_ids=[],
                file_count=0,
                region_filter=region_filter,
                conversation=session.conversation,
                quota=post_quota,
            )

        summary, evidence, grounding_mode, used_web_search, used_file_input, file_ids = self._generate_summary(
            session=session,
            provider=provider,
            file_candidates=file_candidates,
        )
        model_used = self._model_for_trace(provider, used_web_search=used_web_search)
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
                model=model_used,
                question=self._profile_brief(session),
                intent="admissions_recommendation_summary",
                datasets=[item.source_path for item in file_candidates[:20]],
                tables=[],
                filters=[{"region_filter": region_filter}],
                evidence=[item.model_dump(mode="json") for item in evidence],
                grounding_mode=grounding_mode,
                used_web_search=used_web_search,
                used_file_input=used_file_input,
                file_ids=file_ids,
                file_count=len(file_ids),
                region_filter=region_filter,
                recommended_tracks=self._recommended_tracks(summary),
                answer=self._render_summary_text(summary),
            )
        )

        post_quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        session.stage = CounselingStage.active_counseling if post_quota.can_chat else CounselingStage.completed
        session.final_summary = summary
        session.final_evidence = evidence
        session.last_trace_id = trace.trace_id
        session.last_provider = provider.profile.provider
        session.last_model = model_used
        session.last_grounding_mode = grounding_mode
        session.last_used_web_search = used_web_search
        session.last_used_file_input = used_file_input
        session.last_file_ids = file_ids
        session.last_file_count = len(file_ids)
        session.last_region_filter = region_filter
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
            model=model_used,
            grounding_mode=grounding_mode,
            used_web_search=used_web_search,
            used_file_input=used_file_input,
            file_ids=file_ids,
            file_count=len(file_ids),
            region_filter=region_filter,
            conversation=session.conversation,
            quota=post_quota,
        )

    def followup_response_if_cached(
        self,
        session_id: str,
        client_request_id: str,
        *,
        actor_type: ActorType,
        actor_id: str,
    ) -> FollowupResponse | None:
        """Return a follow-up response if this client_request_id was already answered."""
        session = self.session_store.get(session_id)
        if session.final_summary is None:
            return None
        existing = self._find_followup_response(session, client_request_id)
        if existing is None:
            return None
        return FollowupResponse(
            session_id=session.session_id,
            stage=session.stage,
            answer=existing.content,
            trace_id=session.last_trace_id,
            grounding_mode=session.last_grounding_mode,
            used_web_search=session.last_used_web_search,
            used_file_input=session.last_used_file_input,
            file_ids=session.last_file_ids,
            file_count=session.last_file_count,
            region_filter=session.last_region_filter or self._region_filter(session),
            conversation=session.conversation,
            quota=self.usage_service.quota_for_actor(actor_type, actor_id),
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
            raise ValueError("Generate the recommendation summary before follow-up questions.")
        if not payload.question.strip():
            raise ValueError("Question must not be empty.")

        existing = self._find_followup_response(session, payload.client_request_id)
        if existing is not None:
            return FollowupResponse(
                session_id=session.session_id,
                stage=session.stage,
                answer=existing.content,
                trace_id=session.last_trace_id,
                grounding_mode=session.last_grounding_mode,
                used_web_search=session.last_used_web_search,
                used_file_input=session.last_used_file_input,
                file_ids=session.last_file_ids,
                file_count=session.last_file_count,
                region_filter=session.last_region_filter or self._region_filter(session),
                conversation=session.conversation,
                quota=self.usage_service.quota_for_actor(actor_type, actor_id),
            )

        quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        if not quota.can_chat:
            raise ValueError("Usage limit exceeded for this recommendation session.")

        provider = self.provider_factory.create()
        file_candidates = self._select_file_candidates(session, question=payload.question)
        region_filter = self._region_filter(session)
        answer, grounding_mode, used_web_search, used_file_input, file_ids = self._generate_followup_answer(
            session=session,
            question=payload.question,
            provider=provider,
            file_candidates=file_candidates,
        )
        model_used = self._model_for_trace(provider, used_web_search=used_web_search)
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
                model=model_used,
                question=payload.question,
                intent="admissions_followup",
                datasets=[item.source_path for item in file_candidates[:20]],
                tables=[],
                filters=[{"region_filter": region_filter}],
                evidence=[item.model_dump(mode="json") for item in self._candidates_to_evidence(file_candidates[:5])],
                grounding_mode=grounding_mode,
                used_web_search=used_web_search,
                used_file_input=used_file_input,
                file_ids=file_ids,
                file_count=len(file_ids),
                region_filter=region_filter,
                recommended_tracks=self._recommended_tracks(session.final_summary),
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
        session.last_model = model_used
        session.last_grounding_mode = grounding_mode
        session.last_used_web_search = used_web_search
        session.last_used_file_input = used_file_input
        session.last_file_ids = file_ids
        session.last_file_count = len(file_ids)
        session.last_region_filter = region_filter
        post_quota = self.usage_service.quota_for_actor(actor_type, actor_id)
        session.stage = CounselingStage.active_counseling if post_quota.can_chat else CounselingStage.completed
        self.session_store.save(session)
        return FollowupResponse(
            session_id=session.session_id,
            stage=session.stage,
            answer=answer,
            trace_id=trace.trace_id,
            grounding_mode=grounding_mode,
            used_web_search=used_web_search,
            used_file_input=used_file_input,
            file_ids=file_ids,
            file_count=len(file_ids),
            region_filter=region_filter,
            conversation=session.conversation,
            quota=post_quota,
        )

    def _select_file_candidates(
        self,
        session: CounselingSession,
        *,
        question: str | None,
    ) -> list[AdmissionsFileCandidate]:
        catalog = self.manifest_store.load()
        candidates = list_admissions_files(self.settings, catalog)
        filtered = filter_admissions_files(
            candidates,
            region_text=session.user_profile.target_region,
            question_text=question,
        )
        return rank_and_cap_admissions_candidates(
            session.user_profile,
            filtered,
            max_files=self.settings.openai_summary_max_candidate_files,
        )

    def _region_filter(self, session: CounselingSession) -> str | None:
        region = (session.user_profile.target_region or "").strip()
        return region or None

    def _generate_summary(
        self,
        *,
        session: CounselingSession,
        provider: Any,
        file_candidates: list[AdmissionsFileCandidate],
    ) -> tuple[CounselingSummary, list[EvidenceItem], str, bool, bool, list[str]]:
        batch_size = max(1, self.settings.openai_file_batch_size)
        if len(file_candidates) <= batch_size:
            summary, used_web_search, used_file_input, file_ids = self._generate_summary_for_batch(
                session=session,
                provider=provider,
                batch=file_candidates,
            )
            return (
                summary,
                self._candidates_to_evidence(file_candidates[:5]),
                "file_inputs",
                used_web_search,
                used_file_input,
                file_ids,
            )

        batch_summaries: list[CounselingSummary] = []
        all_file_ids: list[str] = []
        any_web_search = False
        for batch in _chunked(file_candidates, batch_size):
            partial, used_web_search, used_file_input, file_ids = self._generate_summary_for_batch(
                session=session,
                provider=provider,
                batch=batch,
            )
            batch_summaries.append(partial)
            all_file_ids.extend(file_ids)
            any_web_search = any_web_search or used_web_search
            if not used_file_input:
                continue

        final_summary = self._synthesize_batch_summaries(session, provider, batch_summaries)
        return (
            final_summary,
            self._candidates_to_evidence(file_candidates[:5]),
            "file_inputs_batched",
            any_web_search,
            True,
            _dedupe_strings(all_file_ids),
        )

    def _generate_summary_for_batch(
        self,
        *,
        session: CounselingSession,
        provider: Any,
        batch: list[AdmissionsFileCandidate],
    ) -> tuple[CounselingSummary, bool, bool, list[str]]:
        selected_files = [item.source_path for item in batch]
        allow_web_enrichment = self._summary_needs_web_enrichment(session)
        messages = build_summary_messages(
            session=session,
            selected_files=selected_files,
            allow_web_enrichment=allow_web_enrichment,
        )
        file_paths = [item.path for item in batch]
        if isinstance(provider, OpenAIProvider):
            parse_plans: list[tuple[bool, bool]] = [
                (True, allow_web_enrichment),
                (False, allow_web_enrichment),
            ]
            if allow_web_enrichment:
                parse_plans.append((False, False))

            last_error: str | None = None
            for use_reasoning, use_web in parse_plans:
                try:
                    response = provider.responses_parse(
                        messages,
                        text_format=CounselingSummary,
                        use_web_search=use_web,
                        file_paths=file_paths,
                        use_reasoning=use_reasoning,
                    )
                    summary = counseling_summary_from_parsed_or_text(
                        response.parsed,
                        response.content or "",
                    )
                    if summary is None:
                        last_error = (
                            f"parsed_empty reasoning={use_reasoning} web={use_web} "
                            f"content_len={len(response.content or '')}"
                        )
                        logger.warning("admissions summary: %s", last_error)
                        continue
                    summary = self._sanitize_recommendation_summary(summary)
                    if summary.recommended_options:
                        return (
                            summary,
                            response.used_web_search,
                            response.used_file_input,
                            response.file_ids,
                        )
                    last_error = f"recommended_options_empty reasoning={use_reasoning} web={use_web}"
                    logger.warning("admissions summary: %s", last_error)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("admissions summary OpenAI error: %s", last_error, exc_info=True)

            if last_error:
                logger.warning("admissions summary exhausted retries; last=%s", last_error)

        if isinstance(provider, OllamaProvider):
            try:
                response = provider.responses_parse(
                    messages,
                    text_format=CounselingSummary,
                    use_web_search=False,
                    file_paths=None,
                    use_reasoning=False,
                )
                summary = counseling_summary_from_parsed_or_text(
                    response.parsed,
                    response.content or "",
                )
                if summary is not None:
                    summary = self._sanitize_recommendation_summary(summary)
                    if summary.recommended_options:
                        return (
                            summary,
                            False,
                            False,
                            [],
                        )
            except Exception as exc:
                if isinstance(exc, ConnectionError):
                    logger.warning(
                        "admissions summary Ollama 연결 실패(대상 %s). 데몬이 떠 있는지 확인하세요.",
                        ollama_base_url_for_settings(self.settings),
                    )
                logger.warning("admissions summary Ollama error: %s", exc, exc_info=True)

        return self._deterministic_summary(session, batch), False, False, []

    def _summary_needs_web_enrichment(self, session: CounselingSession) -> bool:
        if not self.settings.openai_web_search_enabled:
            return False
        profile = session.user_profile
        joined = " ".join(
            [
                profile.residence_preference or "",
                ", ".join(profile.constraints),
                profile.notes or "",
            ]
        )
        return any(term in joined for term in ("기숙사", "등록금", "학비", "생활관"))

    def _synthesize_batch_summaries(
        self,
        session: CounselingSession,
        provider: Any,
        batch_summaries: list[CounselingSummary],
    ) -> CounselingSummary:
        if not batch_summaries:
            return self._deterministic_summary(session, [])
        if len(batch_summaries) == 1:
            return batch_summaries[0]
        try:
            messages = build_batch_synthesis_messages(
                session=session,
                batch_summaries=[item.model_dump(mode="json") for item in batch_summaries],
            )
            response = provider.generate(messages, response_model=CounselingSummary, temperature=0.2)
            if response.parsed:
                merged = CounselingSummary.model_validate(response.parsed)
                return self._sanitize_recommendation_summary(merged)
        except Exception:
            pass

        option_map: dict[tuple[str, str, str], RecommendationOption] = {}
        next_actions: list[str] = []
        for summary in batch_summaries:
            for option in summary.recommended_options:
                key = (option.university, option.major, option.track)
                if key not in option_map:
                    option_map[key] = option
            next_actions.extend(summary.next_actions)
        merged_options = list(option_map.values())[:5]
        return CounselingSummary(
            overview="전국 모집결과를 여러 묶음으로 나눠 비교한 뒤, 전체 기준에서 다시 정리한 추천안입니다.",
            recommended_options=merged_options,
            next_actions=_dedupe_strings(next_actions)[:4],
            closing_message="전국 단위로 넓게 봤을 때도, 지금은 이 조합들부터 우선 검토하는 흐름이 가장 안정적입니다.",
        )

    def _generate_followup_answer(
        self,
        *,
        session: CounselingSession,
        question: str,
        provider: Any,
        file_candidates: list[AdmissionsFileCandidate],
    ) -> tuple[str, str, bool, bool, list[str]]:
        batch = file_candidates[: max(1, self.settings.openai_file_batch_size)]
        selected_files = [item.source_path for item in batch]
        allow_web_enrichment = self.settings.openai_web_search_enabled and looks_like_living_info_question(question)
        messages = build_followup_messages(
            session=session,
            question=question,
            selected_files=selected_files,
            allow_web_enrichment=allow_web_enrichment,
            max_conversation_messages=self.settings.followup_context_message_limit(),
        )
        file_paths = [item.path for item in batch] if batch else []

        if isinstance(provider, OpenAIProvider):
            try:
                response = provider.responses_create(
                    messages,
                    use_web_search=allow_web_enrichment,
                    file_paths=file_paths if file_paths else None,
                )
                if response.content.strip():
                    return (
                        response.content.strip(),
                        "web_enrichment" if allow_web_enrichment else "file_inputs_followup",
                        response.used_web_search,
                        response.used_file_input,
                        response.file_ids,
                    )
            except Exception:
                pass

        if isinstance(provider, OllamaProvider):
            try:
                response = provider.responses_create(
                    messages,
                    use_web_search=False,
                    file_paths=None,
                )
                if response.content.strip():
                    return (
                        response.content.strip(),
                        "ollama_followup",
                        False,
                        False,
                        [],
                    )
            except Exception as exc:
                if isinstance(exc, ConnectionError):
                    logger.warning(
                        "follow-up Ollama 연결 실패(대상 %s).",
                        ollama_base_url_for_settings(self.settings),
                    )
                logger.warning("follow-up Ollama error: %s", exc, exc_info=True)

        return self._deterministic_followup_answer(session, question), "deterministic_followup", False, False, []

    @staticmethod
    def _sanitize_recommendation_summary(summary: CounselingSummary) -> CounselingSummary:
        seen: set[tuple[str, str, str]] = set()
        unique: list[RecommendationOption] = []
        for opt in summary.recommended_options:
            key = (opt.university.strip(), opt.major.strip(), opt.track.strip())
            if key == ("", "", ""):
                continue
            if key in seen:
                continue
            seen.add(key)
            unique.append(opt)
        if len(unique) > 5:
            unique = unique[:5]
        return summary.model_copy(update={"recommended_options": unique})

    def _deterministic_summary(
        self,
        session: CounselingSession,
        batch: list[AdmissionsFileCandidate],
    ) -> CounselingSummary:
        profile = session.user_profile
        region = profile.target_region or "희망 지역"
        if batch:
            files_blob = "\n".join(f"- {c.source_path}" for c in batch[:10])
            return CounselingSummary(
                overview=(
                    "첨부된 모집결과 파일은 후보로 올라왔지만, 이번 호출에서 모델이 표를 읽어 "
                    "학과·전형·경쟁률·등급컷 등이 담긴 구조화 추천을 반환하지 못했습니다. "
                    "추측으로 학과·전형을 채우지 않았습니다. API 키, 네트워크, 응답 파싱 오류를 확인해 주세요."
                ),
                recommended_options=[
                    RecommendationOption(
                        university="(구조화 추천 실패)",
                        major="파일 표의 학과(모집단위) 열에 있는 실제 명칭만 사용해야 합니다.",
                        track="항목마다 전형 하나만. 파일의 전형명 열 표기를 그대로 쓰세요.",
                        campus_or_region=region,
                        fit_reason="무지성 추천을 피하기 위해 구체 조합을 비워 두었습니다.",
                        evidence_summary="분석 대상으로 올라온 파일(일부):\n" + files_blob,
                        metrics_line=None,
                        source_file_hint=batch[0].source_path if batch else None,
                        next_step="백엔드 로그에서 OpenAI 오류를 확인한 뒤 ingestion 후 추천을 다시 실행해 보세요.",
                    )
                ],
                next_actions=[
                    "서버에서 OpenAI 응답/에러 로그 확인",
                    "`POST /api/v1/ingestion/run`으로 catalog 갱신 후 재시도",
                    "새 세션에서 추천 완료 다시 실행",
                ],
                closing_message="모집결과 표의 실제 행을 읽을 수 있을 때만 학과·전형·수치가 포함된 추천이 나갑니다.",
            )

        interests = ", ".join(profile.interest_fields[:2]) if profile.interest_fields else "관심 전공"
        track_hint = ", ".join(profile.track_preferences[:2]) if profile.track_preferences else "지원 가능한 전형"
        return CounselingSummary(
            overview=f"{region} 기준으로 사용할 모집결과 파일 후보가 비어 있습니다.",
            recommended_options=[
                RecommendationOption(
                    university=f"{region} 권역 대학",
                    major=interests,
                    track=track_hint,
                    campus_or_region=region,
                    fit_reason="파일 후보가 없어 일반적인 방향만 안내합니다.",
                    evidence_summary="`Data` 아래 엑셀 후보가 없거나 경로를 확인해 주세요.",
                    next_step="모집결과 xlsx를 `Data`에 두고 ingestion을 실행한 뒤 다시 시도하세요.",
                )
            ],
            next_actions=[
                "`Data`에 모집결과 파일 추가",
                "ingestion 실행 후 재시도",
            ],
            closing_message="파일이 준비되면 표에서 읽은 학과·전형·수치 기반으로 추천할 수 있습니다.",
        )

    def _missing_file_summary(self, session: CounselingSession) -> CounselingSummary:
        profile = session.user_profile
        interests = ", ".join(profile.interest_fields[:2]) if profile.interest_fields else "관심 전공"
        region = profile.target_region or "전국"
        track_hint = ", ".join(profile.track_preferences[:2]) if profile.track_preferences else "지원 전형"
        return CounselingSummary(
            overview=(
                f"현재 `Data`와 catalog에서 {region} 기준 모집결과 파일을 찾지 못해, "
                "실제 입시 추천을 확정적으로 만들 수 없는 상태입니다."
            ),
            recommended_options=[
                RecommendationOption(
                    university="모집결과 파일 확인 필요",
                    major=interests,
                    track=track_hint,
                    campus_or_region=region,
                    fit_reason="추천 엔진은 실제 모집결과 파일을 붙여서 전형별로 비교할 때 가장 정확하게 동작합니다.",
                    evidence_summary="현재 세션에서는 첨부 가능한 모집결과 파일이 비어 있어 안내형 응답으로 전환했습니다.",
                    next_step="`Data` 폴더에 대학별 모집결과 또는 모집요강 파일을 넣고 ingestion을 다시 실행해 주세요.",
                )
            ],
            next_actions=[
                "대학별 모집결과 파일을 `Data` 아래에 추가하기",
                "ingestion을 다시 실행해 catalog 메타를 갱신하기",
                "그 뒤 같은 조건으로 추천을 다시 생성하기",
            ],
            closing_message="실제 추천은 파일이 준비되는 즉시 다시 계산할 수 있습니다.",
        )

    def _deterministic_followup_answer(self, session: CounselingSession, question: str) -> str:
        summary = session.final_summary
        if summary is None or not summary.recommended_options:
            return (
                "지금 질문은 가능하면 해당 학교의 모집결과와 공식 안내를 같이 보는 쪽이 정확합니다. "
                "학교명이나 지역을 조금 더 좁혀 주시면 바로 다시 정리해드릴게요."
            )
        lead = summary.recommended_options[0]
        if looks_like_living_info_question(question):
            return (
                f"{lead.university} 쪽 생활 조건이 중요하신 거죠.\n\n"
                "이 항목은 학교 공식 안내 기준으로 확인하는 게 가장 정확합니다. "
                "기숙사 여부, 신입생 우선 선발, 등록금·장학 기준 정도를 같이 보면 판단이 빨라집니다."
            )
        return (
            f"지금 질문까지 반영하면, 우선순위는 여전히 **{lead.university} / {lead.major} / {lead.track}** 조합이 가장 앞에 있습니다. "
            "원하시면 다음 답변에서는 이 후보를 기준으로 학교를 더 줄이거나, 같은 학과의 다른 전형과 비교해드릴 수 있어요."
        )

    def _candidates_to_evidence(self, candidates: list[AdmissionsFileCandidate]) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                dataset_title=item.title,
                school_name=item.school_name,
                region=item.region,
                source_path=item.source_path,
                excerpt=f"{item.kind} 파일을 추천 근거로 사용했습니다.",
            )
            for item in candidates
        ]

    def _recommended_tracks(self, summary: CounselingSummary | None) -> list[str]:
        if summary is None:
            return []
        return _dedupe_strings(option.track for option in summary.recommended_options if option.track)

    def _profile_brief(self, session: CounselingSession) -> str:
        profile = session.user_profile
        parts: list[str] = []
        if profile.interest_fields:
            parts.append(f"관심 분야: {', '.join(profile.interest_fields)}")
        if profile.student_record_grade:
            parts.append(f"내신: {profile.student_record_grade}")
        if profile.mock_exam_score:
            parts.append(f"수능/모의고사: {profile.mock_exam_score}")
        if profile.converted_score:
            parts.append(f"환산점수: {profile.converted_score}")
        if profile.admission_plan:
            parts.append(f"지원 축: {profile.admission_plan}")
        if profile.track_preferences:
            parts.append(f"전형 후보: {', '.join(profile.track_preferences)}")
        if profile.target_region:
            parts.append(f"희망 지역: {profile.target_region}")
        return " | ".join(parts) or "admissions recommendation"

    def _model_for_trace(self, provider: Any, *, used_web_search: bool) -> str:
        if used_web_search and isinstance(provider, OpenAIProvider):
            return provider.resolved_web_search_model()
        return provider.profile.chat_model

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
        counselor_message = latest_assistant.content if latest_assistant else "추천을 위해 필요한 정보를 먼저 확인할게요."
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
        parts = [summary.overview.strip()]
        if summary.recommended_options:
            bullets = []
            for item in summary.recommended_options[:4]:
                line = f"- **{item.university} / {item.major} / {item.track}**: {item.fit_reason}"
                if item.metrics_line:
                    line += f" | 모집결과 수치: {item.metrics_line}"
                if item.source_file_hint:
                    line += f" | 근거 파일: {item.source_file_hint}"
                if item.evidence_summary:
                    line += f"\n  근거: {item.evidence_summary}"
                if item.next_step:
                    line += f"\n  다음: {item.next_step}"
                bullets.append(line)
            parts.append("우선 추천 조합은 이쪽입니다.\n" + "\n".join(bullets))
        if summary.next_actions:
            parts.append(
                "다음으로 이렇게 움직이면 됩니다.\n"
                + "\n".join(f"- {item}" for item in summary.next_actions[:3])
            )
        parts.append(summary.closing_message.strip())
        return "\n\n".join(part for part in parts if part)
