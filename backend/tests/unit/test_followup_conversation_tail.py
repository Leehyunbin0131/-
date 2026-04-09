from __future__ import annotations

import json

from app.chat.models import ConversationMessage, ConversationRole, CounselingSession, CounselingSummary
from app.chat.prompts import build_followup_messages


def test_followup_includes_summary_message_not_only_last_six() -> None:
    """Long intake + summary: tail must include summary assistant, not drop it like [-6:]."""
    filler = [
        ConversationMessage(role=ConversationRole.user, kind="intake_answer", content="a"),
        ConversationMessage(role=ConversationRole.assistant, kind="intake_prompt", content="b"),
    ] * 10
    summary_msg = ConversationMessage(
        role=ConversationRole.assistant,
        kind="summary",
        content="요약 본문과 질문 두 가지",
    )
    session = CounselingSession(
        conversation=[*filler, summary_msg],
        final_summary=CounselingSummary(
            overview="s",
            recommended_options=[],
            next_actions=[],
            closing_message="c",
        ),
    )
    msgs = build_followup_messages(
        session=session,
        question="웹보안, 기숙사",
        selected_files=[],
        allow_web_enrichment=False,
    )
    payload = json.loads(msgs[1].content)
    recent = payload["recent_conversation"]
    kinds = [m["kind"] for m in recent]
    assert "summary" in kinds
    assert recent[0]["kind"] == "summary"
