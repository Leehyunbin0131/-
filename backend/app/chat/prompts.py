from __future__ import annotations

import json

from app.chat.models import ConversationRole, CounselingSession
from app.llm.base import ChatMessage

_DEFAULT_FOLLOWUP_CONVERSATION_MAX_MESSAGES = 72

_SUMMARY_SYSTEM = """당신은 한국어로 답하는 대학 입시 추천 분석가입니다.

첨부된 모집결과/모집요강 원본(엑셀 등)이 유일한 1차 근거입니다. 웹검색·상식으로 학과명·전형명·수치를 만들어내지 마세요.
각 `recommended_options` 항목은 **대학 + 학과 + 전형** 조합 하나입니다.

필수 규칙(위반 시 잘못된 답변):
1) `university`, `major`, `track`은 첨부 파일 표에 **실제로 존재하는 행**에서 읽은 문자열만 쓰세요. 사용자의 관심 분야 문구를 major에 그대로 붙이지 마세요.
2) `track`에는 **전형을 정확히 하나만** 넣으세요. "학생부교과, 학생부종합"처럼 쉼표로 여러 전형을 한 필드에 넣지 마세요. 여러 전형이 필요하면 `recommended_options` 항목을 나누세요.
3) 각 `recommended_options`마다 `evidence_summary`에 해당 행의 **숫자**를 인용하세요(모집인원, 경쟁률, 학생부등급 평균·컷, 환산점수 등 파일 열에 있는 그대로). 수치가 표에 없으면 그 사실을 밝히고, 그 행은 추천에서 빼거나 다른 행을 고르세요.
4) `metrics_line`에는 한 줄로 요약하세요. 예: "2025학년도 정시 기준 경쟁률 5.2:1, 학생부등급평균 3.9, 85%컷 4.4" — 반드시 파일에서 읽은 값만.
5) `source_file_hint`에는 그 근거 행을 읽은 첨부 파일의 상대 경로 또는 파일명을 넣으세요.
6) 사용자 관심과 일치하는 학과 행이 파일에 없으면 `overview`에 한 줄로 알리고, **가장 근접한 실제 행만** 제한적으로 추천하거나 추천 개수를 줄이세요. 학교에 없는 학과명을 만들지 마세요.
7) 추천은 3~5개가 적당합니다. 확률·합격 보장 표현은 금지하고 "과거 모집결과 기준으로 상대적으로 유리해 보인다" 수준으로 쓰세요.
8) 기숙사/등록금은 파일·웹 보강 규칙에 따라 `dorm_note`/`tuition_note`에만 넣으세요.
9) 출력은 반드시 지정된 구조화 JSON 스키마를 따르세요.
"""

_FOLLOWUP_SYSTEM = """당신은 같은 학생과 계속 대화 중인 대학 입시 추천 분석가입니다.

- 이미 확보한 성적/지역/전형 정보를 반복해서 묻지 마세요.
- 질문이 대학/학과/전형 비교면 첨부 모집결과 표에 있는 행·수치를 인용해 결론부터 답하세요. 표에 없는 학과·전형·숫자는 만들지 마세요.
- 질문이 기숙사/등록금/캠퍼스 생활이면 공식 안내 기준의 사실 답변을 우선하세요.
- 말투는 간결하고 친절하게, 보고서처럼 길지 않게 쓰세요.
"""


def _conversation_tail_for_followup(
    session: CounselingSession,
    *,
    max_messages: int,
) -> list[dict[str, object]]:
    msgs = session.conversation
    if not msgs:
        return []
    summary_idx: int | None = None
    for i in range(len(msgs) - 1, -1, -1):
        message = msgs[i]
        if message.role == ConversationRole.assistant and message.kind == "summary":
            summary_idx = i
            break
    cap = max(8, max_messages)
    tail = msgs[summary_idx:] if summary_idx is not None else msgs[-cap:]
    if len(tail) > cap:
        tail = tail[-cap:]
    return [item.model_dump(mode="json") for item in tail]


def build_summary_messages(
    *,
    session: CounselingSession,
    selected_files: list[str],
    allow_web_enrichment: bool,
) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content=_SUMMARY_SYSTEM),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "task": "admissions_recommendation",
                    "opening_question": session.opening_question,
                    "user_profile": session.user_profile.model_dump(mode="json"),
                    "intake_answers": [answer.model_dump(mode="json") for answer in session.answers],
                    "selected_files": selected_files,
                    "allow_web_enrichment": allow_web_enrichment,
                },
                ensure_ascii=False,
            ),
        ),
    ]


def build_batch_synthesis_messages(
    *,
    session: CounselingSession,
    batch_summaries: list[dict[str, object]],
) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                _SUMMARY_SYSTEM
                + "\n추가 규칙: 여러 배치의 부분 추천을 합쳐 최종 추천 3~5개만 남기세요. "
                "항목마다 전형은 하나, 학과·수치는 첨부 파일 표에 있는 것만, `metrics_line`에 수치를 한 줄로 요약하세요."
            ),
        ),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "task": "admissions_recommendation_synthesis",
                    "opening_question": session.opening_question,
                    "user_profile": session.user_profile.model_dump(mode="json"),
                    "batch_summaries": batch_summaries,
                },
                ensure_ascii=False,
            ),
        ),
    ]


def build_followup_messages(
    *,
    session: CounselingSession,
    question: str,
    selected_files: list[str],
    allow_web_enrichment: bool,
    max_conversation_messages: int = _DEFAULT_FOLLOWUP_CONVERSATION_MAX_MESSAGES,
) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content=_FOLLOWUP_SYSTEM),
        ChatMessage(
            role="user",
            content=json.dumps(
                {
                    "task": "admissions_followup",
                    "question": question,
                    "current_summary": session.final_summary.model_dump(mode="json")
                    if session.final_summary is not None
                    else None,
                    "user_profile": session.user_profile.model_dump(mode="json"),
                    "selected_files": selected_files,
                    "allow_web_enrichment": allow_web_enrichment,
                    "recent_conversation": _conversation_tail_for_followup(
                        session,
                        max_messages=max_conversation_messages,
                    ),
                },
                ensure_ascii=False,
            ),
        ),
    ]
