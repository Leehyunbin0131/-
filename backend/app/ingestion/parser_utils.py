from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str, *, prefix: str = "item") -> str:
    stripped = value.strip()
    if not stripped:
        return prefix
    ascii_candidate = (
        unicodedata.normalize("NFKD", stripped).encode("ascii", "ignore").decode("ascii")
    )
    candidate = ascii_candidate or stripped
    candidate = re.sub(r"[^0-9A-Za-z]+", "_", candidate).strip("_").lower()
    if candidate:
        return candidate
    digest = hashlib.sha1(stripped.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def extract_snapshot_date(path: Path) -> str | None:
    text = path.stem
    date_match = re.search(r"(20\d{2})(\d{2})(\d{2})", text)
    if date_match:
        return "".join(date_match.groups())
    year_match = re.search(r"(20\d{2})", text)
    if year_match:
        return year_match.group(1)
    return None


def dataset_topic_from_path(relative_path: Path) -> str:
    parents = list(relative_path.parts[:-1])
    if not parents:
        return "general"
    return " / ".join(parents)


def build_dataset_id(relative_path: Path) -> str:
    folder_bits = [slugify(part, prefix="folder") for part in relative_path.parts[:-1]]
    file_bit = slugify(relative_path.stem, prefix="dataset")
    return "_".join(part for part in [*folder_bits, file_bit] if part)


def normalize_column_names(values: list[object]) -> list[str]:
    seen: dict[str, int] = {}
    normalized: list[str] = []
    for index, value in enumerate(values):
        text = str(value).strip() if value is not None else ""
        if not text or text.lower() == "nan":
            text = f"column_{index + 1}"
        cleaned = re.sub(r"\s+", " ", text)
        key = slugify(cleaned, prefix=f"column_{index + 1}")
        count = seen.get(key, 0)
        seen[key] = count + 1
        normalized.append(key if count == 0 else f"{key}_{count + 1}")
    return normalized


def clean_header_labels(values: list[object]) -> list[str]:
    labels: list[str] = []
    for index, value in enumerate(values):
        text = str(value).strip() if value is not None else ""
        if not text or text.lower() == "nan":
            text = f"column_{index + 1}"
        labels.append(re.sub(r"\s+", " ", text))
    return labels


def detect_header_row(frame: pd.DataFrame, max_rows: int = 10) -> int:
    if frame.empty:
        return 0
    limit = min(max_rows, len(frame.index))
    best_row = 0
    best_score = -1
    for idx in range(limit):
        row = frame.iloc[idx]
        score = int(row.notna().sum())
        if score > best_score:
            best_score = score
            best_row = idx
    return best_row


def normalize_sheet_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if cleaned.empty:
        return cleaned

    header_row_index = detect_header_row(cleaned)
    header_values = cleaned.iloc[header_row_index].tolist()
    header_labels = clean_header_labels(header_values)
    column_names = normalize_column_names(header_labels)
    body = cleaned.iloc[header_row_index + 1 :].copy()
    body.columns = column_names
    body = body.dropna(axis=0, how="all").reset_index(drop=True)
    body.attrs["original_column_labels"] = dict(zip(column_names, header_labels, strict=True))
    return body


def _normalize_scalar(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


def prepare_for_parquet(frame: pd.DataFrame) -> pd.DataFrame:
    safe = frame.copy()
    for column in safe.columns:
        series = safe[column].map(_normalize_scalar)
        inferred = pd.api.types.infer_dtype(series, skipna=True)
        if inferred.startswith("mixed"):
            safe[column] = series.map(lambda value: None if value is None else str(value)).astype("string")
            continue
        converted = series.convert_dtypes()
        if str(converted.dtype) == "object":
            safe[column] = converted.map(lambda value: None if pd.isna(value) else str(value)).astype("string")
        else:
            safe[column] = converted
    return safe


def infer_semantic_role(column_name: str, dtype: str) -> str | None:
    lowered = column_name.lower()
    if "year" in lowered or "연도" in column_name or "년도" in column_name or "년" in column_name:
        return "year"
    if (
        "region" in lowered
        or "city" in lowered
        or "지역" in column_name
        or "시도" in column_name
        or "시군구" in column_name
    ):
        return "region"
    if (
        "school" in lowered
        or "university" in lowered
        or "학교" in column_name
        or "대학" in column_name
    ):
        return "school"
    if (
        "major" in lowered
        or "department" in lowered
        or "학과" in column_name
        or "전공" in column_name
    ):
        return "major"
    if "취업" in column_name or "진학" in column_name or "비율" in column_name or "률" in column_name:
        return "metric"
    if dtype.startswith(("int", "float")):
        return "metric"
    return None


def summarize_dataframe(frame: pd.DataFrame, limit: int = 5) -> str:
    if frame.empty:
        return "Empty table"
    preview = frame.head(limit).fillna("").astype(str).to_dict(orient="records")
    column_list = ", ".join(frame.columns.tolist())
    return f"columns={column_list}; preview={preview}"
