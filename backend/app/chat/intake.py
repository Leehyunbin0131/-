from __future__ import annotations

import re

from app.chat.models import IntakeQuestion, UserProfile


INTAKE_QUESTIONS: list[IntakeQuestion] = [
    IntakeQuestion(
        question_id="current_stage",
        profile_field="current_stage",
        prompt="지금 어떤 단계에 가장 가까우신가요?",
        help_text="현재 위치를 알아야 진학 중심으로 볼지, 취업 중심으로 볼지 정할 수 있어요.",
        options=[
            "고등학생",
            "대학생",
            "휴학생",
            "취업 준비 중",
            "이직 고민 중",
        ],
    ),
    IntakeQuestion(
        question_id="goals",
        profile_field="goals",
        prompt="이번 상담에서 가장 얻고 싶은 결과는 무엇인가요?",
        help_text="예: 취업 잘 되는 방향, 적성에 맞는 학과, 지역을 고려한 선택지 정리",
    ),
    IntakeQuestion(
        question_id="interests",
        profile_field="interests",
        prompt="관심 있거나 끌리는 분야를 알려주세요.",
        help_text="쉼표로 여러 개 적어도 됩니다. 예: IT, 데이터, 디자인",
        allows_multiple=True,
    ),
    IntakeQuestion(
        question_id="avoidances",
        profile_field="avoidances",
        prompt="반대로 피하고 싶은 방향이나 잘 맞지 않는 일은 있나요?",
        help_text="예: 사람 상대가 너무 많은 일, 지방 근무, 긴 학업 기간",
        allows_multiple=True,
    ),
    IntakeQuestion(
        question_id="priorities",
        profile_field="priorities",
        prompt="의사결정에서 가장 중요한 기준은 무엇인가요?",
        help_text="예: 취업 안정성, 적성, 연봉, 학비, 지역, 경쟁 강도",
        options=[
            "취업 안정성",
            "적성",
            "연봉",
            "학비 부담",
            "지역",
            "경쟁 강도",
        ],
        allows_multiple=True,
    ),
    IntakeQuestion(
        question_id="target_region",
        profile_field="target_region",
        prompt="선호하는 지역이 있나요?",
        help_text="예: 서울, 수도권, 상관없음",
    ),
    IntakeQuestion(
        question_id="constraints",
        profile_field="constraints",
        prompt="현실적으로 고려해야 할 제약이 있다면 알려주세요.",
        help_text="예: 성적, 경제적 여건, 이동 가능 여부, 가족 상황",
        allows_multiple=True,
    ),
    IntakeQuestion(
        question_id="decision_pain",
        profile_field="decision_pain",
        prompt="지금 가장 결정이 어려운 지점을 한 문장으로 말해주실 수 있나요?",
        help_text="예: 적성을 따라가야 할지 취업률을 우선해야 할지 모르겠어요.",
    ),
]


def get_intake_questions() -> list[IntakeQuestion]:
    return list(INTAKE_QUESTIONS)


def get_question(question_id: str) -> IntakeQuestion:
    for question in INTAKE_QUESTIONS:
        if question.question_id == question_id:
            return question
    raise ValueError(f"Unknown intake question: {question_id}")


def get_next_question(profile: UserProfile, answered_question_ids: set[str]) -> IntakeQuestion | None:
    for question in INTAKE_QUESTIONS:
        if question.question_id in answered_question_ids:
            continue
        if is_question_satisfied(profile, question):
            continue
        return question
    return None


def is_question_satisfied(profile: UserProfile, question: IntakeQuestion) -> bool:
    value = getattr(profile, question.profile_field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def apply_answer(profile: UserProfile, question: IntakeQuestion, answer: str | list[str]) -> UserProfile:
    if question.profile_field in {"goals", "interests", "avoidances", "priorities", "constraints"}:
        setattr(profile, question.profile_field, to_string_list(answer))
    else:
        if isinstance(answer, list):
            text = ", ".join(item.strip() for item in answer if item.strip())
        else:
            text = answer.strip()
        setattr(profile, question.profile_field, text)
    return profile


def to_string_list(answer: str | list[str]) -> list[str]:
    if isinstance(answer, list):
        values = [item.strip() for item in answer if item.strip()]
        return dedupe(values)
    chunks = [part.strip() for part in re.split(r"[,/\n;]+", answer) if part.strip()]
    if not chunks and answer.strip():
        chunks = [answer.strip()]
    return dedupe(chunks)


def answered_count(profile: UserProfile) -> int:
    return sum(1 for question in INTAKE_QUESTIONS if is_question_satisfied(profile, question))


def total_questions() -> int:
    return len(INTAKE_QUESTIONS)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
