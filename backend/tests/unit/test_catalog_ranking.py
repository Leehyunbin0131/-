from __future__ import annotations

from pathlib import Path

from app.chat.admissions_files import AdmissionsFileCandidate
from app.chat.catalog_ranking import rank_and_cap_admissions_candidates, score_admissions_candidate
from app.chat.models import UserProfile


def _c(path: str, school: str | None = None, kind: str = "result") -> AdmissionsFileCandidate:
    return AdmissionsFileCandidate(
        path=Path(path),
        source_path=path,
        title=Path(path).stem,
        kind=kind,
        school_name=school,
        region=None,
        year=None,
    )


def test_score_prefers_interest_and_track_in_text() -> None:
    profile = UserProfile(
        interest_fields=["컴퓨터"],
        track_preferences=["학생부교과"],
        blocked_tracks=[],
    )
    high = _c("경기대_컴퓨터공학_학생부교과.xlsx", "경기대학교")
    low = _c("other_대학_인문학과.xlsx", "다른대학교")
    assert score_admissions_candidate(profile, high) > score_admissions_candidate(profile, low)


def test_blocked_track_lowers_score() -> None:
    profile = UserProfile(
        interest_fields=[],
        track_preferences=[],
        blocked_tracks=["논술"],
    )
    bad = _c("school_논술전형.xlsx")
    good = _c("school_학생부교과.xlsx")
    assert score_admissions_candidate(profile, good) > score_admissions_candidate(profile, bad)


def test_rank_and_cap_truncates() -> None:
    profile = UserProfile()
    candidates = [_c(f"f{i}.xlsx") for i in range(10)]
    out = rank_and_cap_admissions_candidates(profile, candidates, max_files=3)
    assert len(out) == 3
