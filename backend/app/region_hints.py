"""Korean administrative region hints for path matching and catalog `region` fields.

카탈로그·파일 경로에 섞인 `경상북도`, `경산시`, `영남권` 등을 짧은 토큰(경북, 대구 …)으로
풀어서 지역 필터(수도권·영남권 등)와 맞춥니다.
"""

from __future__ import annotations

import re
from pathlib import Path

# (긴 표기, 필터·검색용 짧은 토큰) — 긴 문자열을 먼저 치환해야 할 때는 아래 튜플 순서 유지
_ADMIN_TO_SHORT: tuple[tuple[str, str], ...] = (
    ("강원특별자치도", "강원"),
    ("전북특별자치도", "전북"),
    ("전라특별자치도", "전북"),
    ("제주특별자치도", "제주"),
    ("세종특별자치시", "세종"),
    ("서울특별시", "서울"),
    ("부산광역시", "부산"),
    ("대구광역시", "대구"),
    ("인천광역시", "인천"),
    ("광주광역시", "광주"),
    ("대전광역시", "대전"),
    ("울산광역시", "울산"),
    ("경상북도", "경북"),
    ("경상남도", "경남"),
    ("전라북도", "전북"),
    ("전라남도", "전남"),
    ("충청북도", "충북"),
    ("충청남도", "충남"),
)

# 경로 세그먼트(시·군·구 이름) → 짧은 도·광역시 토큰
_SIGUNGU_TO_PROVINCE: dict[str, str] = {
    # 경북
    "경산시": "경북",
    "경주시": "경북",
    "구미시": "경북",
    "김천시": "경북",
    "문경시": "경북",
    "상주시": "경북",
    "안동시": "경북",
    "영주시": "경북",
    "영천시": "경북",
    "포항시": "경북",
    "의성군": "경북",
    "청송군": "경북",
    "영양군": "경북",
    "영덕군": "경북",
    "청도군": "경북",
    "고령군": "경북",
    "성주군": "경북",
    "칠곡군": "경북",
    "예천군": "경북",
    "봉화군": "경북",
    "울진군": "경북",
    "울릉군": "경북",
    # 경남
    "창원시": "경남",
    "김해시": "경남",
    "양산시": "경남",
    "진주시": "경남",
    "통영시": "경남",
    "사천시": "경남",
    "밀양시": "경남",
    "거제시": "경남",
    "함안군": "경남",
    "거창군": "경남",
    "창녕군": "경남",
    "고성군": "경남",
    "하동군": "경남",
    "합천군": "경남",
    "남해군": "경남",
    "함양군": "경남",
    "의령군": "경남",
    # 광역시 구 (다른 시와 겹치지 않는 것만)
    "달서구": "대구",
    "수성구": "대구",
    "달성군": "대구",
    "해운대구": "부산",
    "사하구": "부산",
    "금정구": "부산",
    "기장군": "부산",
    # 수도권
    "수원시": "경기",
    "성남시": "경기",
    "고양시": "경기",
    "용인시": "경기",
    "부천시": "경기",
    "안산시": "경기",
    "안양시": "경기",
    "남양주시": "경기",
    "화성시": "경기",
    "평택시": "경기",
    "의정부시": "경기",
    "시흥시": "경기",
    "파주시": "경기",
    "김포시": "경기",
    "광명시": "경기",
    "군포시": "경기",
    "하남시": "경기",
    "오산시": "경기",
    "이천시": "경기",
    "안성시": "경기",
    "의왕시": "경기",
    "양주시": "경기",
    "구리시": "경기",
    "포천시": "경기",
    "여주시": "경기",
    "동두천시": "경기",
    "과천시": "경기",
    "가평군": "경기",
    "양평군": "경기",
    "연천군": "경기",
    "강화군": "인천",
    "옹진군": "인천",
    # 충청
    "천안시": "충남",
    "공주시": "충남",
    "보령시": "충남",
    "아산시": "충남",
    "서산시": "충남",
    "논산시": "충남",
    "계룡시": "충남",
    "당진시": "충남",
    "청주시": "충북",
    "충주시": "충북",
    "제천시": "충북",
    "보은군": "충북",
    "옥천군": "충북",
    "영동군": "충북",
    "증평군": "충북",
    "진천군": "충북",
    "괴산군": "충북",
    "음성군": "충북",
    "단양군": "충북",
    # 호남
    "전주시": "전북",
    "군산시": "전북",
    "익산시": "전북",
    "정읍시": "전북",
    "남원시": "전북",
    "김제시": "전북",
    "목포시": "전남",
    "여수시": "전남",
    "순천시": "전남",
    "나주시": "전남",
    "광양시": "전남",
    # 강원
    "춘천시": "강원",
    "원주시": "강원",
    "강릉시": "강원",
    "동해시": "강원",
    "태백시": "강원",
    "속초시": "강원",
    "삼척시": "강원",
}

_MACRO_PATH_EXPANSION: dict[str, tuple[str, ...]] = {
    "영남권": ("부산", "대구", "울산", "경북", "경남"),
    "수도권": ("서울", "경기", "인천"),
    "충청권": ("대전", "세종", "충북", "충남"),
    "호남권": ("광주", "전북", "전남"),
    "경기도권": ("경기",),
}

# 인제스션 `_infer_region`에서 경로 키워드 스캔 순서 (짧은 토큰)
REGION_KEYWORDS: tuple[str, ...] = (
    "서울",
    "경기",
    "인천",
    "강원",
    "대전",
    "세종",
    "충북",
    "충남",
    "대구",
    "경북",
    "부산",
    "울산",
    "경남",
    "광주",
    "전북",
    "전남",
    "제주",
)


def squash_admin_region_names(text: str) -> str:
    s = text
    for long_form, short in _ADMIN_TO_SHORT:
        s = s.replace(long_form, short)
    return s


def normalize_catalog_region_label(raw: str | None) -> str | None:
    if raw is None:
        return None
    stripped = str(raw).strip()
    if not stripped:
        return None
    return squash_admin_region_names(stripped)


def _path_segments(path: str) -> list[str]:
    return [p for p in re.split(r"[\\/]+", path.replace("/", "\\")) if p]


def segment_location_tokens(path: str) -> tuple[str, ...]:
    """경로에 등장하는 시·군·구·권역 폴더명에서 도·광역 토큰을 추출합니다."""
    hints: list[str] = []
    seen: set[str] = set()
    for seg in _path_segments(path):
        if seg in _MACRO_PATH_EXPANSION:
            for t in _MACRO_PATH_EXPANSION[seg]:
                if t not in seen:
                    seen.add(t)
                    hints.append(t)
        prov = _SIGUNGU_TO_PROVINCE.get(seg)
        if prov and prov not in seen:
            seen.add(prov)
            hints.append(prov)
    return tuple(hints)


def build_region_match_blob(region: str | None, source_path: str, school_name: str | None = None) -> str:
    """지역 필터(부분 문자열) 비교용 문자열. 시도 정규화 + 시군구→도 + 학교명(대구대 등) 포함."""
    path = source_path.replace("/", "\\")
    parts = [region or "", path, school_name or ""]
    parts.extend(segment_location_tokens(path))
    blob = " ".join(parts)
    return squash_admin_region_names(blob)


def infer_region_token_from_path(relative_path: str, school_name: str | None = None) -> str | None:
    """데이터셋 `region` 필드에 넣을 단일 토큰 (우선 시군구 매핑, 그다음 키워드 스캔)."""
    norm = relative_path.replace("/", "\\")
    for seg in _path_segments(norm):
        prov = _SIGUNGU_TO_PROVINCE.get(seg)
        if prov:
            return prov
        if seg in _MACRO_PATH_EXPANSION:
            # 권역 폴더만 있고 하위 시도가 없으면 첫 토큰 대신 None보다는 대표값을 주지 않음 → 키워드로
            pass
    blob = squash_admin_region_names(f"{norm} {school_name or ''}")
    for kw in REGION_KEYWORDS:
        if kw in blob:
            return kw
    return None


def infer_region_token_for_relative_path(relative_path: Path, school_name: str | None) -> str | None:
    return infer_region_token_from_path(str(relative_path).replace("/", "\\"), school_name)
