from __future__ import annotations

import json
from typing import Sequence

from app.chat.models import CounselingSession, EvidenceItem, QuestionIntent, UserProfile
from app.llm.base import ChatMessage


def build_selection_messages(
    *,
    search_query: str,
    user_profile: UserProfile,
    intent: QuestionIntent,
    candidate_tables: list[dict[str, object]],
) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You select the best statistical table for a grounded counseling assistant. "
                "Choose only from the provided candidates. Prefer exact numeric evidence for "
                "numeric questions and broader outcome tables for counseling questions."
            ),
        ),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "intent": intent.value,
                    "question": search_query,
                    "user_profile": user_profile.model_dump(mode="json"),
                    "candidate_tables": candidate_tables,
                },
                ensure_ascii=False,
            ),
        ),
    ]


def build_summary_messages(
    *,
    session: CounselingSession,
    evidence: Sequence[EvidenceItem],
    guidance: Sequence[str],
) -> list[ChatMessage]:
    evidence_payload = [item.model_dump(mode="json") for item in evidence]
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a grounded counselor for education and employment decisions. "
                "Only use the provided evidence. If the evidence is insufficient, say so clearly. "
                "Do not invent statistics, years, institutions, or promises. "
                "Return a counselor-style summary that is warm, direct, and practical."
            ),
        ),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "intent": QuestionIntent.counseling.value,
                    "opening_question": session.opening_question,
                    "stage": session.stage.value,
                    "user_profile": session.user_profile.model_dump(mode="json"),
                    "intake_answers": [answer.model_dump(mode="json") for answer in session.answers],
                    "guidance_hints": list(guidance),
                    "evidence": evidence_payload,
                },
                ensure_ascii=False,
            ),
        ),
    ]


def build_followup_messages(
    *,
    session: CounselingSession,
    question: str,
    evidence: Sequence[EvidenceItem],
) -> list[ChatMessage]:
    evidence_payload = [item.model_dump(mode="json") for item in evidence]
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a grounded counselor continuing an existing session. "
                "Stay warm, concise, and practical. Use only the provided evidence and existing summary. "
                "If the evidence is weak, say what is still uncertain instead of inventing facts."
            ),
        ),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "question": question,
                    "current_summary": session.final_summary.model_dump(mode="json")
                    if session.final_summary is not None
                    else None,
                    "user_profile": session.user_profile.model_dump(mode="json"),
                    "recent_conversation": [
                        item.model_dump(mode="json") for item in session.conversation[-6:]
                    ],
                    "evidence": evidence_payload,
                },
                ensure_ascii=False,
            ),
        ),
    ]
