from __future__ import annotations

from app.chat.models import CounselingSummary, RecommendationOption
from app.chat.summary_recovery import counseling_summary_from_parsed_or_text, counseling_summary_from_text


def test_counseling_summary_from_text_plain_json() -> None:
    raw = (
        '{"overview":"요약",'
        '"recommended_options":[{"university":"A대","major":"컴공","track":"학생부교과",'
        '"fit_reason":"이유","evidence_summary":"근거"}],'
        '"next_actions":[],"closing_message":"끝"}'
    )
    s = counseling_summary_from_text(raw)
    assert s is not None
    assert s.recommended_options[0].university == "A대"


def test_counseling_summary_from_text_fenced_json() -> None:
    raw = """다음은 결과입니다.
```json
{"overview":"o","recommended_options":[{"university":"B대","major":"전자","track":"정시","fit_reason":"f","evidence_summary":"e"}],"next_actions":[],"closing_message":"c"}
```
"""
    s = counseling_summary_from_text(raw)
    assert s is not None
    assert s.overview == "o"


def test_counseling_summary_from_parsed_or_text_prefers_parsed() -> None:
    data = {
        "overview": "parsed",
        "recommended_options": [
            {
                "university": "C대",
                "major": "수학",
                "track": "논술",
                "fit_reason": "x",
                "evidence_summary": "y",
            }
        ],
        "next_actions": [],
        "closing_message": "z",
    }
    s = counseling_summary_from_parsed_or_text(data, "not json")
    assert s is not None
    assert s.overview == "parsed"


def test_counseling_summary_from_parsed_or_text_fallback_to_content() -> None:
    model = CounselingSummary(
        overview="x",
        recommended_options=[
            RecommendationOption(
                university="D대",
                major="국어",
                track="학생부종합",
                fit_reason="f",
                evidence_summary="e",
            )
        ],
        next_actions=[],
        closing_message="c",
    )
    dumped = model.model_dump_json()
    s = counseling_summary_from_parsed_or_text(None, f"prefix\n{dumped}\ntrailer")
    assert s is not None
    assert s.recommended_options[0].university == "D대"
