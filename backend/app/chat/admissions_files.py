from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd

from app.catalog.models import CatalogState, DatasetRecord
from app.config import Settings
from app.region_hints import (
    build_region_match_blob,
    infer_region_token_from_path,
    normalize_catalog_region_label,
)

# 파일명·경로에 흔한 표기(대학 공지 엑셀). "모집결과" 문구가 없어도 실제 모집결과인 경우가 많음.
_ADMISSIONS_RESULT_HINTS = (
    "모집결과",
    "전형결과",
    "입시결과",
    "충원합격",
    "충원현황",
    "최초합격",
    "합격현황",
    "합격자현황",
    "경쟁률",
)
_ADMISSIONS_GUIDE_HINTS = ("모집요강", "요강")
# OpenAI Responses `input_file`에 올릴 모집·요강 원문(스프레드시트는 API 쪽 시트 요약으로 PDF보다 토큰 효율적).
_LLM_ADMISSIONS_SUFFIXES = (".xls", ".xlsx", ".xlsm", ".pdf")
_REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "서울": ("서울",),
    "경기": ("경기",),
    "인천": ("인천",),
    "수도권": ("서울", "경기", "인천"),
    "경기도권": ("경기",),
    "충청권": ("대전", "세종", "충북", "충남"),
    "영남권": ("부산", "대구", "울산", "경북", "경남"),
    "호남권": ("광주", "전북", "전남"),
    "강원권": ("강원",),
    "제주": ("제주",),
    "전국": (),
    "상관없음": (),
}


@dataclass(slots=True)
class AdmissionsFileCandidate:
    path: Path
    source_path: str
    title: str
    kind: str
    school_name: str | None = None
    region: str | None = None
    year: str | None = None


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _candidate_kind(text: str) -> str | None:
    if _contains_any(text, _ADMISSIONS_RESULT_HINTS):
        return "result"
    if _contains_any(text, _ADMISSIONS_GUIDE_HINTS):
        return "guide"
    return None


def is_llm_admissions_path(path: Path) -> bool:
    return path.suffix.lower() in _LLM_ADMISSIONS_SUFFIXES


def structured_input_tier(path: Path) -> int:
    """LLM 파일 입력 우선순위(낮을수록 선호). 스프레드시트는 API가 행·요약을 압축, PDF는 텍스트+이미지로 토큰 증가 가능."""
    s = path.suffix.lower()
    if s in (".xlsx", ".xlsm", ".xls"):
        return 0
    if s == ".pdf":
        return 1
    return 2


def _pairing_key(candidate: AdmissionsFileCandidate) -> tuple[str, str, str]:
    text = f"{candidate.source_path} {candidate.title} {candidate.school_name or ''}"
    school = (candidate.school_name or _extract_school_name(candidate.source_path) or "").strip()
    if not school:
        parts = Path(candidate.source_path.replace("\\", "/")).parts
        school = parts[-2] if len(parts) >= 2 else candidate.source_path
    year_m = re.search(r"(20\d{2})", text)
    year = year_m.group(1) if year_m else "unknown"
    has_s = "수시" in text
    has_j = "정시" in text
    if has_s and has_j:
        phase = "혼합"
    elif has_j:
        phase = "정시"
    elif has_s:
        phase = "수시"
    else:
        phase = "기타"
    return (school, year, phase)


def dedupe_prefer_structured_over_pdf(candidates: list[AdmissionsFileCandidate]) -> list[AdmissionsFileCandidate]:
    """같은 학교·연도·수시/정시 묶음에서 엑셀이 있으면 PDF는 제외(동일 근거 중복 + PDF 토큰 부담 감소)."""
    buckets: dict[tuple[str, str, str], list[AdmissionsFileCandidate]] = defaultdict(list)
    for c in candidates:
        buckets[_pairing_key(c)].append(c)
    out: list[AdmissionsFileCandidate] = []
    for items in buckets.values():
        structured = [x for x in items if structured_input_tier(x.path) == 0]
        if structured:
            out.extend(structured)
            continue
        out.extend(items)
    return out


def _candidate_sort_key(item: AdmissionsFileCandidate) -> tuple[bool, int, str]:
    return (item.kind != "result", structured_input_tier(item.path), item.source_path)


def extract_school_names(text: str) -> list[str]:
    matches = set(re.findall(r"([가-힣A-Za-z0-9]+대학교|[가-힣A-Za-z0-9]+대)", text))
    cleaned = [item for item in matches if item not in {"대학", "대학교"}]
    return sorted(cleaned, key=len, reverse=True)


def _extract_school_name(text: str) -> str | None:
    names = extract_school_names(text)
    return names[0] if names else None


def normalize_region_tokens(raw_region: str | None) -> tuple[str, ...]:
    if raw_region is None:
        return ()
    stripped = raw_region.strip()
    if not stripped:
        return ()
    if stripped in _REGION_ALIASES:
        return _REGION_ALIASES[stripped]
    for alias, values in _REGION_ALIASES.items():
        if alias in stripped:
            return values
    return (stripped,)


def build_school_region_map(catalog: CatalogState) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for table in catalog.tables.values():
        joined = f"{table.title} {table.source_path}"
        if "학교명" not in joined and "대학현황지표" not in joined and "전국대학별학과정보표준데이터" not in joined:
            continue
        parquet_path = Path(table.parquet_path)
        if not parquet_path.exists():
            continue
        try:
            frame = pd.read_parquet(parquet_path)
        except Exception:
            continue
        school_col = next((col for col in frame.columns if "학교명" in str(col)), None)
        region_col = next(
            (col for col in frame.columns if any(token in str(col) for token in ("시도명", "지역", "소재지"))),
            None,
        )
        if school_col is None or region_col is None:
            continue
        for _, row in frame[[school_col, region_col]].dropna().iterrows():
            school = str(row[school_col]).strip()
            raw_region = str(row[region_col]).strip()
            region = normalize_catalog_region_label(raw_region) or raw_region
            if school and region and school not in mapping:
                mapping[school] = region
    return mapping


def _candidate_from_dataset(
    settings: Settings,
    dataset: DatasetRecord,
    school_region_map: dict[str, str],
) -> AdmissionsFileCandidate | None:
    source_path = dataset.source_path.replace("/", "\\")
    joined = f"{dataset.title} {source_path}"
    path = settings.data_root / Path(source_path)
    if not path.exists() or not is_llm_admissions_path(path):
        return None
    kind = dataset.document_type or _candidate_kind(joined) or "result"
    school_name = dataset.school_name or _extract_school_name(joined)
    raw_region = dataset.region or school_region_map.get(school_name or "", None)
    region = (normalize_catalog_region_label(raw_region) or raw_region) if raw_region else None
    return AdmissionsFileCandidate(
        path=path,
        source_path=source_path,
        title=dataset.title,
        kind=kind,
        school_name=school_name,
        region=region,
        year=dataset.year,
    )


def list_admissions_files(settings: Settings, catalog: CatalogState) -> list[AdmissionsFileCandidate]:
    school_region_map = build_school_region_map(catalog)
    candidates: list[AdmissionsFileCandidate] = []
    seen_paths: set[str] = set()
    for dataset in catalog.datasets.values():
        candidate = _candidate_from_dataset(settings, dataset, school_region_map)
        if candidate is None:
            continue
        if str(candidate.path) in seen_paths:
            continue
        seen_paths.add(str(candidate.path))
        candidates.append(candidate)

    # catalog에 없는 새 파일도 Data에만 있으면 포함 (PDF는 ingestion 대상이 아니어도 LLM 파일 입력 후보)
    discovered: set[str] = set()
    for ext in _LLM_ADMISSIONS_SUFFIXES:
        for path in settings.data_root.rglob(f"*{ext}"):
            if path.suffix.lower() != ext:
                continue
            key = str(path.resolve())
            if key in discovered:
                continue
            discovered.add(key)
            if str(path) in seen_paths:
                continue
            if not is_llm_admissions_path(path):
                continue
            joined = str(path.relative_to(settings.data_root))
            kind = _candidate_kind(joined) or "result"
            school_name = _extract_school_name(joined)
            inferred = infer_region_token_from_path(joined, school_name)
            candidates.append(
                AdmissionsFileCandidate(
                    path=path,
                    source_path=joined,
                    title=path.stem,
                    kind=kind,
                    school_name=school_name,
                    region=inferred,
                    year=None,
                )
            )
            seen_paths.add(str(path))

    candidates = dedupe_prefer_structured_over_pdf(candidates)
    return sorted(candidates, key=_candidate_sort_key)


def filter_admissions_files(
    candidates: list[AdmissionsFileCandidate],
    *,
    region_text: str | None = None,
    question_text: str | None = None,
) -> list[AdmissionsFileCandidate]:
    filtered = list(candidates)
    school_names = extract_school_names(question_text or "")
    if school_names:
        narrowed = [
            item
            for item in filtered
            if any(name in f"{item.school_name or ''} {item.source_path}" for name in school_names)
        ]
        if narrowed:
            filtered = narrowed

    region_tokens = normalize_region_tokens(region_text)
    if region_tokens:
        narrowed = [
            item
            for item in filtered
            if any(
                token in build_region_match_blob(item.region, item.source_path, item.school_name)
                for token in region_tokens
            )
        ]
        filtered = narrowed
    return sorted(filtered, key=_candidate_sort_key)
