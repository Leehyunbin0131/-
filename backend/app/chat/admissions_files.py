from __future__ import annotations

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
_SPREADSHEET_SUFFIXES = (".xls", ".xlsx", ".xlsm")
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


def _is_spreadsheet_path(path: Path) -> bool:
    return path.suffix.lower() in _SPREADSHEET_SUFFIXES


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
    if not path.exists() or not _is_spreadsheet_path(path):
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

    # catalog에 없는 새 파일도 Data에만 있으면 포함 (ingestion 전에 넣은 경우)
    for pattern in _SPREADSHEET_SUFFIXES:
        for path in settings.data_root.rglob(f"*{pattern}"):
            if str(path) in seen_paths:
                continue
            if not _is_spreadsheet_path(path):
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
    return sorted(candidates, key=lambda item: (item.kind != "result", item.source_path))


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
    return sorted(filtered, key=lambda item: (item.kind != "result", item.source_path))
