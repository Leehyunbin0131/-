from __future__ import annotations

import json
from typing import Sequence

from pydantic import BaseModel

from app.chat.models import SessionAnswerRequest, SessionStartRequest, UserProfile
from app.chat.orchestrator import CounselingOrchestrator
from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile
from app.usage.models import ActorType


class FakeCounselingProvider(LLMProvider):
    def __init__(self) -> None:
        self.profile = ModelProfile(
            provider="fake",
            chat_model="fake-chat",
            embedding_model="fake-embed",
            supports_tools=False,
            supports_structured_output=True,
        )

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        tools=None,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        payload = json.loads(messages[-1].content)
        if response_model is not None:
            if "candidate_tables" in payload:
                table_id = payload["candidate_tables"][0]["table_id"]
                parsed = {
                    "table_id": table_id,
                    "rationale": "Selected the highest-ranked table for employment evidence.",
                    "limit": 2,
                }
            else:
                parsed = {
                    "situation_summary": "You are a high_school user focused on software careers in Seoul.",
                    "recommended_directions": [
                        {
                            "title": "Prioritize employment-backed software pathways",
                            "fit_reason": "The user values employment outcomes and software-related work.",
                            "evidence_summary": "Employment data from the selected table supports this direction.",
                            "action_tip": "Compare two or three software-related options first.",
                        }
                    ],
                    "risks_and_tradeoffs": [
                        {
                            "direction_title": "Prioritize employment-backed software pathways",
                            "risk": "Over-optimizing for one metric can hide fit problems.",
                            "reality_check": "Use employment statistics as a filter, not the only decision rule.",
                        }
                    ],
                    "next_actions": [
                        "Compare software-related options in Seoul.",
                        "Check cost and admission difficulty next.",
                    ],
                    "closing_message": "Start by narrowing the field to a few realistic options.",
                }
            return GenerationResponse(
                provider=self.profile.provider,
                model=model or self.profile.chat_model,
                content=json.dumps(parsed),
                parsed=parsed,
            )
        return GenerationResponse(provider=self.profile.provider, model=model or self.profile.chat_model, content="")

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "employment" in lowered else 0.0,
                    1.0 if "major" in lowered else 0.0,
                    1.0 if "seoul" in lowered or "region" in lowered else 0.0,
                ]
            )
        return EmbeddingResponse(
            provider=self.profile.provider,
            model=model or self.profile.embedding_model or "fake-embed",
            dimensions=3,
            vectors=vectors,
        )


class FakeProviderFactory:
    def __init__(self, provider: FakeCounselingProvider) -> None:
        self.provider = provider

    def create(self, provider_name: str | None = None) -> FakeCounselingProvider:
        return self.provider


def test_grounded_answer_pipeline(container, settings) -> None:
    container.ingestion_pipeline.run()
    provider = FakeCounselingProvider()
    catalog = container.manifest_store.load()
    container.vector_index.rebuild(provider, catalog)

    orchestrator = CounselingOrchestrator(
        settings=settings,
        manifest_store=container.manifest_store,
        session_store=container.session_store,
        vector_index=container.vector_index,
        query_runner=container.query_runner,
        provider_factory=FakeProviderFactory(provider),
        trace_store=container.trace_store,
        usage_service=container.usage_service,
    )

    start = orchestrator.start_session(
        SessionStartRequest(
            opening_question="I want advice using employment data in Seoul.",
            user_profile=UserProfile(target_region="Seoul"),
        ),
        actor_type=ActorType.guest,
        actor_id="guest-eval",
        guest_id="guest-eval",
    )
    assert start.stage.value == "intake"
    assert start.current_question is not None
    assert start.current_question.question_id == "current_stage"

    answers = {
        "current_stage": "high_school",
        "goals": "employment outcomes in Seoul",
        "interests": ["software"],
        "avoidances": ["sales"],
        "priorities": ["employment stability", "region"],
        "target_region": "Seoul",
        "constraints": ["budget"],
        "decision_pain": "I do not know whether to optimize for fit or employment rate.",
    }

    progress = start
    while progress.stage.value == "intake":
        question_id = progress.current_question.question_id
        progress = orchestrator.answer_intake_question(
            progress.session_id,
            SessionAnswerRequest(answer=answers[question_id]),
            actor_type=ActorType.guest,
            actor_id="guest-eval",
        )

    assert progress.stage.value == "ready_for_summary"

    response = orchestrator.generate_counseling_summary(
        progress.session_id,
        actor_type=ActorType.guest,
        actor_id="guest-eval",
    )
    assert response.summary.situation_summary
    assert response.summary.recommended_directions
    assert response.summary.risks_and_tradeoffs
    assert response.evidence
    assert response.trace_id is not None
    assert response.quota.trial_used == 1
