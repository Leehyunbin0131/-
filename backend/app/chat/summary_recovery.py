from __future__ import annotations

import json
import re
from typing import Any

from app.chat.models import CounselingSummary


def counseling_summary_from_text(raw: str) -> CounselingSummary | None:
    """`output_text`에 JSON만 섞여 나온 경우 마지막 수단으로 파싱."""
    text = (raw or "").strip()
    if not text:
        return None
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
    try:
        return CounselingSummary.model_validate(json.loads(text))
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return CounselingSummary.model_validate(json.loads(text[start : end + 1]))
    except Exception:
        return None


def counseling_summary_from_parsed_or_text(parsed: Any | None, content: str) -> CounselingSummary | None:
    if parsed is not None:
        try:
            return CounselingSummary.model_validate(parsed)
        except Exception:
            pass
    return counseling_summary_from_text(content)
