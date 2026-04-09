from __future__ import annotations

import re

from app.chat.models import IntakeQuestion, UserProfile


INTAKE_QUESTIONS: list[IntakeQuestion] = [
    IntakeQuestion(
        question_id="student_status",
        profile_field="student_status",
        prompt="현재 수험 상황에 가장 가까운 상태를 골라주세요.",
        help_text="상황에 따라 추천할 대학과 전형 해석이 조금 달라집니다.",
        options=[
            "고3",
            "고2 이하",
            "재수/N수",
            "검정고시/기타",
        ],
        input_type="single_select",
    ),
    IntakeQuestion(
        question_id="interest_fields",
        profile_field="interest_fields",
        prompt="관심 있는 전공/분야를 알려주세요.",
        help_text="여러 개 선택해도 됩니다. 추천은 이 분야 기준으로 좁혀집니다.",
        options=[
            "컴퓨터공학",
            "소프트웨어",
            "사이버보안",
            "인공지능",
            "데이터/통계",
            "전자/반도체",
            "기계/자동차",
            "간호/보건",
            "경영/경제",
            "디자인/미디어",
        ],
        allows_multiple=True,
        input_type="multi_select",
    ),
    IntakeQuestion(
        question_id="student_record_grade",
        profile_field="student_record_grade",
        prompt="내신 등급을 적어주세요.",
        help_text="예: 3.2, 2등급 후반, 아직 모름",
        input_type="text",
        placeholder="예: 3.2",
    ),
    IntakeQuestion(
        question_id="mock_exam_score",
        profile_field="mock_exam_score",
        prompt="수능/모의고사 성적 또는 백분위를 적어주세요.",
        help_text="예: 국수영탐 백분위 82/76/3/71, 아직 없음",
        input_type="text",
        placeholder="예: 국수영탐 백분위 82/76/3/71",
    ),
    IntakeQuestion(
        question_id="converted_score",
        profile_field="converted_score",
        prompt="학교/학원 기준 환산점수가 있으면 적어주세요.",
        help_text="없으면 '없음'이라고 적어도 됩니다.",
        input_type="text",
        placeholder="예: 531.4 / 없음",
    ),
    IntakeQuestion(
        question_id="admission_plan",
        profile_field="admission_plan",
        prompt="지원 축은 어떻게 생각하고 있나요?",
        help_text="수시/정시 어느 쪽 비중이 큰지 알아야 전형 추천이 정확해집니다.",
        options=["수시 위주", "정시 위주", "수시/정시 둘 다", "아직 모르겠음"],
        input_type="single_select",
    ),
    IntakeQuestion(
        question_id="track_preferences",
        profile_field="track_preferences",
        prompt="검토 중인 세부 전형이 있나요?",
        help_text="모르겠다면 '아직 모르겠음'만 골라도 됩니다.",
        options=[
            "학생부교과",
            "학생부종합",
            "논술",
            "정시 일반",
            "정시 특기/특별전형",
            "아직 모르겠음",
        ],
        allows_multiple=True,
        input_type="multi_select",
    ),
    IntakeQuestion(
        question_id="target_region",
        profile_field="target_region",
        prompt="희망 지역을 알려주세요.",
        help_text="특정 지역만 원하면 그 지역 대학 모집결과만 분석합니다.",
        options=[
            "서울",
            "경기",
            "인천",
            "수도권",
            "충청권",
            "영남권",
            "호남권",
            "강원권",
            "제주",
            "전국",
        ],
        input_type="single_select",
    ),
    IntakeQuestion(
        question_id="residence_preference",
        profile_field="residence_preference",
        prompt="통학/기숙사 조건은 어떻게 생각하고 있나요?",
        help_text="기숙사 가능 여부는 웹검색으로 같이 확인합니다.",
        options=["통학 가능", "기숙사 선호", "둘 다 가능", "상관없음"],
        input_type="single_select",
    ),
    IntakeQuestion(
        question_id="constraints",
        profile_field="constraints",
        prompt="추가 제약 조건이 있다면 적어주세요.",
        help_text="예: 학비 부담, 지방은 어려움, 4년제 우선, 취업 안정성 우선",
        allows_multiple=True,
        input_type="text",
        placeholder="쉼표로 여러 개 적을 수 있어요.",
    ),
    IntakeQuestion(
        question_id="blocked_tracks",
        profile_field="blocked_tracks",
        prompt="현실적으로 어려운 전형이나 제외할 조건이 있나요?",
        help_text="예: 논술 준비 안 함, 학생부종합 부담, 면접 많은 전형 피하고 싶음",
        allows_multiple=True,
        input_type="text",
        placeholder="예: 논술 제외, 면접 부담",
    ),
    IntakeQuestion(
        question_id="notes",
        profile_field="notes",
        prompt="마지막으로 꼭 반영했으면 하는 사정이 있다면 적어주세요.",
        help_text="예: 사이버보안 쪽 선호, 집에서 멀면 힘듦, 등록금 부담 큼",
        input_type="text",
        placeholder="없으면 비워두지 말고 '없음'이라고 적어주세요.",
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
    if question.profile_field in {"interest_fields", "track_preferences", "constraints", "blocked_tracks"}:
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
