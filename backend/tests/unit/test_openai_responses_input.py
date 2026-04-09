from __future__ import annotations

import json

from app.chat.models import CounselingSession, UserProfile
from app.chat.prompts import build_followup_messages, build_summary_messages
from app.llm.base import ChatMessage, GenerationResponse
from app.llm.providers.openai_provider import OpenAIProvider


def test_messages_to_responses_input_shape() -> None:
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="hi"),
    ]
    out = OpenAIProvider.messages_to_responses_input(messages)
    assert out == [
        {"type": "message", "role": "system", "content": "sys"},
        {"type": "message", "role": "user", "content": "hi"},
    ]


def test_build_summary_payload_contains_selected_files_and_web_flag() -> None:
    session = CounselingSession(user_profile=UserProfile())
    msgs = build_summary_messages(
        session=session,
        selected_files=["대학별모집결과/대구대학교/2025모집결과.xlsx"],
        allow_web_enrichment=True,
    )
    payload = json.loads(msgs[1].content)
    assert payload["task"] == "admissions_recommendation"
    assert payload["selected_files"] == ["대학별모집결과/대구대학교/2025모집결과.xlsx"]
    assert payload["allow_web_enrichment"] is True


def test_build_messages_include_new_admissions_fields() -> None:
    session = CounselingSession(user_profile=UserProfile())
    summary_msgs = build_summary_messages(
        session=session,
        selected_files=[],
        allow_web_enrichment=False,
    )
    summary_payload = json.loads(summary_msgs[1].content)
    assert summary_payload["task"] == "admissions_recommendation"
    assert "대학 + 학과 + 전형" in summary_msgs[0].content

    followup_msgs = build_followup_messages(
        session=session,
        question="그 학교 기숙사 있나요?",
        selected_files=[],
        allow_web_enrichment=True,
    )
    followup_payload = json.loads(followup_msgs[1].content)
    assert followup_payload["task"] == "admissions_followup"
    assert followup_payload["allow_web_enrichment"] is True


def test_openai_provider_builds_file_inputs_payload() -> None:
    messages = [
        ChatMessage(role="system", content="system"),
        ChatMessage(role="user", content="hello"),
    ]
    provider = OpenAIProvider(
        api_key="test-key",
        chat_model="gpt-5.4",
        embedding_model="text-embedding-3-small",
    )

    instructions, payload = provider._responses_input_with_files(
        messages,
        file_ids=["file-1", "file-2"],
    )

    assert instructions == "system"
    assert payload[0]["content"][0] == {"type": "input_file", "file_id": "file-1"}
    assert payload[0]["content"][1] == {"type": "input_file", "file_id": "file-2"}
    assert payload[0]["content"][2] == {"type": "input_text", "text": "hello"}


def test_generation_response_tracks_file_count() -> None:
    response = GenerationResponse(
        provider="openai",
        model="gpt-5.4",
        content="ok",
        file_ids=["file-1", "file-2", "file-3"],
        file_count=3,
    )

    assert response.file_count == 3
