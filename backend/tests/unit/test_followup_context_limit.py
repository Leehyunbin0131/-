from __future__ import annotations

from app.config import Settings


def test_followup_context_message_limit_default_covers_thirty_turns() -> None:
    s = Settings(followup_conversation_max_messages=0)
    assert s.followup_context_message_limit() >= 61  # 요약 1 + 질문·답변 30턴(60)


def test_followup_context_message_limit_explicit_override() -> None:
    s = Settings(followup_conversation_max_messages=100)
    assert s.followup_context_message_limit() == 100
