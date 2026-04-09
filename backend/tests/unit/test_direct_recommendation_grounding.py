from __future__ import annotations

from app.chat.models import CounselingSummary, RecommendationOption
from app.chat.orchestrator import CounselingOrchestrator, looks_like_living_info_question
from app.llm.providers.openai_provider import OpenAIProvider


def test_living_info_detector_covers_dorm_and_tuition() -> None:
    assert looks_like_living_info_question("그 학교 기숙사 있나요?")
    assert looks_like_living_info_question("등록금은 어느 정도인가요?")
    assert not looks_like_living_info_question("정시 일반 전형이 더 유리할까요?")


def test_render_summary_text_surfaces_university_major_track() -> None:
    orchestrator = CounselingOrchestrator.__new__(CounselingOrchestrator)
    summary = CounselingSummary(
        overview="경기권 기준으로 현실적인 조합부터 먼저 보는 것이 좋습니다.",
        recommended_options=[
            RecommendationOption(
                university="대구대학교",
                major="컴퓨터공학",
                track="학생부교과",
                fit_reason="현재 조건에서 비교를 시작하기 좋은 후보입니다.",
                evidence_summary="모집결과 파일 기준으로 먼저 확인한 조합입니다.",
                next_step="같은 전형 모집결과를 다시 확인해 보세요.",
            )
        ],
        next_actions=["후보 2~3개로 줄이기"],
        closing_message="지금은 전형 조합부터 먼저 잡는 편이 안정적입니다.",
    )

    rendered = orchestrator._render_summary_text(summary)

    assert "대구대학교 / 컴퓨터공학 / 학생부교과" in rendered
    assert "후보 2~3개로 줄이기" in rendered


def test_recommended_tracks_are_deduped_from_summary() -> None:
    orchestrator = CounselingOrchestrator.__new__(CounselingOrchestrator)
    summary = CounselingSummary(
        overview="요약",
        recommended_options=[
            RecommendationOption(
                university="A대",
                major="컴퓨터공학",
                track="학생부교과",
                fit_reason="이유",
                evidence_summary="근거",
            ),
            RecommendationOption(
                university="B대",
                major="소프트웨어",
                track="학생부교과",
                fit_reason="이유",
                evidence_summary="근거",
            ),
            RecommendationOption(
                university="C대",
                major="사이버보안",
                track="정시 일반",
                fit_reason="이유",
                evidence_summary="근거",
            ),
        ],
        next_actions=[],
        closing_message="마무리",
    )

    assert orchestrator._recommended_tracks(summary) == ["학생부교과", "정시 일반"]


def test_sanitize_recommendation_summary_dedupes_triples() -> None:
    summary = CounselingSummary(
        overview="요약",
        recommended_options=[
            RecommendationOption(
                university="대구대학교",
                major="사이버보안학과",
                track="학생부교과",
                fit_reason="1",
                evidence_summary="a",
            ),
            RecommendationOption(
                university="대구대학교",
                major="사이버보안학과",
                track="학생부교과",
                fit_reason="2",
                evidence_summary="b",
            ),
        ],
        next_actions=[],
        closing_message="끝",
    )
    cleaned = CounselingOrchestrator._sanitize_recommendation_summary(summary)
    assert len(cleaned.recommended_options) == 1
    assert cleaned.recommended_options[0].fit_reason == "1"


def test_openai_provider_detects_web_search_calls_from_responses_payload() -> None:
    class DummyResponse:
        def model_dump(self, mode: str = "json"):  # noqa: ANN202
            return {
                "output": [
                    {
                        "type": "web_search_call",
                        "id": "call_123",
                        "status": "completed",
                    }
                ]
            }

    tool_calls, used_web_search = OpenAIProvider._responses_metadata(DummyResponse())

    assert used_web_search is True
    assert tool_calls[0]["type"] == "web_search_call"
