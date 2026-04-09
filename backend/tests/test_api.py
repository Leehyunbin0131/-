from __future__ import annotations

import time

from app.chat.models import CounselingSummary, RecommendationOption
from app.llm.base import GenerationResponse
from app.llm.providers.openai_provider import OpenAIProvider


def _fake_summary_response(*_, **kwargs) -> GenerationResponse:
    use_web_search = bool(kwargs.get("use_web_search"))
    summary = CounselingSummary(
        overview="경기권과 영남권 모집결과를 비교하면, 현재 입력 조건에서는 학생부교과와 정시 일반을 우선 확인하는 흐름이 좋습니다.",
        recommended_options=[
            RecommendationOption(
                university="경기대학교",
                major="컴퓨터공학부",
                track="학생부교과",
                campus_or_region="경기",
                fit_reason="내신 기준으로 먼저 검토하기 좋은 조합입니다.",
                evidence_summary="모집결과 파일에서 현재 조건과 가장 자연스럽게 맞는 전형으로 정리했습니다.",
                next_step="같은 전형의 최근 모집결과를 한 번 더 비교해 보세요.",
            ),
            RecommendationOption(
                university="대구대학교",
                major="사이버보안학과",
                track="학생부교과",
                campus_or_region="대구",
                fit_reason="보안 관심 분야와 잘 맞는 조합입니다.",
                evidence_summary="대구대학교 모집결과 파일에서 비교 가능한 후보로 확인했습니다.",
                next_step="기숙사와 등록금을 같이 확인해 보세요.",
            ),
        ],
        next_actions=["후보 2개로 줄이기", "기숙사 여부 다시 확인하기"],
        closing_message="최종 지원 전에는 같은 전형명 기준 모집결과를 다시 한 번만 더 맞춰보면 됩니다.",
    )
    return GenerationResponse(
        provider="openai",
        model="gpt-5.4",
        content="",
        parsed=summary.model_dump(mode="json"),
        used_web_search=use_web_search,
        used_file_input=True,
        file_ids=["file-summary-1", "file-summary-2"],
        file_count=2,
    )


def _fake_followup_response(*_, **kwargs) -> GenerationResponse:
    use_web_search = bool(kwargs.get("use_web_search"))
    return GenerationResponse(
        provider="openai",
        model="gpt-5.4",
        content="경기대학교 기준으로 보면 기숙사와 등록금은 공식 안내를 같이 확인하는 게 가장 정확합니다.",
        parsed=None,
        used_web_search=use_web_search,
        used_file_input=not use_web_search,
        file_ids=[] if use_web_search else ["file-followup-1"],
        file_count=0 if use_web_search else 1,
    )


def _post_followup_until_done(client, session_id: str, *, question: str, client_request_id: str):
    body = {"question": question, "client_request_id": client_request_id}
    response = client.post(f"/api/v1/chat/session/{session_id}/message", json=body)
    if response.status_code == 202:
        assert "5분" in response.json()["message"]
        for _ in range(200):
            time.sleep(0.05)
            st = client.get(f"/api/v1/chat/session/{session_id}")
            sess = st.json()["session"]
            if sess.get("followup_job_status") == "failed":
                raise AssertionError(sess.get("followup_job_error") or "followup job failed")
            conv = sess.get("conversation") or []
            if any(
                m.get("kind") == "followup_answer" and m.get("request_id") == client_request_id
                for m in conv
            ):
                break
        else:
            raise AssertionError("followup did not complete in time")
        response = client.post(f"/api/v1/chat/session/{session_id}/message", json=body)
    return response


def test_api_flow(client, monkeypatch) -> None:
    monkeypatch.setattr(OpenAIProvider, "responses_parse", _fake_summary_response)
    monkeypatch.setattr(OpenAIProvider, "responses_create", _fake_followup_response)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ingest = client.post("/api/v1/ingestion/run")
    assert ingest.status_code == 200
    payload = ingest.json()
    assert payload["scanned_files"] == 3
    assert payload["ingested_files"] == 3
    assert payload["table_count"] == 3

    catalog = client.get("/api/v1/catalog/datasets")
    assert catalog.status_code == 200
    assert catalog.json()["count"] == 3

    start = client.post("/api/v1/chat/session/start", json={})
    assert start.status_code == 200
    body = start.json()
    assert body["stage"] == "intake"
    assert body["current_question"]["question_id"] == "student_status"
    assert body["quota"]["remaining"] == 5
    session_id = body["session_id"]

    answers = {
        "student_status": "고3",
        "interest_fields": ["컴퓨터공학", "사이버보안"],
        "student_record_grade": "3.2",
        "mock_exam_score": "국수영탐 백분위 82/76/3/71",
        "converted_score": "없음",
        "admission_plan": "수시 위주",
        "track_preferences": ["학생부교과", "학생부종합"],
        "target_region": "경기",
        "residence_preference": "기숙사 선호",
        "constraints": "학비 부담, 수도권 우선",
        "blocked_tracks": "논술 제외",
        "notes": "웹보안 쪽 관심이 큼",
    }

    while body["stage"] == "intake":
        question_id = body["current_question"]["question_id"]
        response = client.post(
            f"/api/v1/chat/session/{session_id}/answer",
            json={"answer": answers[question_id]},
        )
        assert response.status_code == 200
        body = response.json()

    assert body["stage"] == "ready_for_summary"
    assert body["can_complete"] is True

    session_state = client.get(f"/api/v1/chat/session/{session_id}")
    assert session_state.status_code == 200
    assert session_state.json()["session"]["stage"] == "ready_for_summary"

    complete = client.post(f"/api/v1/chat/session/{session_id}/complete")
    if complete.status_code == 202:
        assert "5분" in complete.json()["message"]
        for _ in range(200):
            time.sleep(0.05)
            st = client.get(f"/api/v1/chat/session/{session_id}")
            sess = st.json()["session"]
            if sess.get("summary_job_status") == "failed":
                raise AssertionError(sess.get("summary_job_error") or "summary job failed")
            if sess.get("final_summary"):
                break
        else:
            raise AssertionError("summary did not complete in time")
        complete = client.post(f"/api/v1/chat/session/{session_id}/complete")
    assert complete.status_code == 200
    summary = complete.json()
    assert summary["summary"]["overview"]
    assert summary["summary"]["recommended_options"]
    assert summary["trace_id"]
    assert summary["used_file_input"] is True
    assert summary["file_count"] == 2
    assert summary["region_filter"] == "경기"
    assert summary["quota"]["used"] == 1
    assert summary["quota"]["remaining"] == 4
    assert summary["stage"] == "active_counseling"

    followup = _post_followup_until_done(
        client,
        session_id,
        question="경기대학교 기숙사 있나요?",
        client_request_id="followup-1",
    )
    assert followup.status_code == 200
    followup_payload = followup.json()
    assert followup_payload["answer"]
    assert followup_payload["used_web_search"] is True
    assert followup_payload["file_count"] == 0
    assert followup_payload["region_filter"] == "경기"
    assert followup_payload["stage"] == "active_counseling"

    for index in range(2, 5):
        response = _post_followup_until_done(
            client,
            session_id,
            question=f"후보를 더 좁혀줘 #{index}",
            client_request_id=f"followup-{index}",
        )
        assert response.status_code == 200
        payload = response.json()
        if index < 4:
            assert payload["stage"] == "active_counseling"
        else:
            assert payload["stage"] == "completed"
            assert payload["quota"]["remaining"] == 0

    blocked = client.post(
        f"/api/v1/chat/session/{session_id}/message",
        json={
            "question": "이제 더 물어봐도 되나요?",
            "client_request_id": "followup-blocked",
        },
    )
    assert blocked.status_code == 429
