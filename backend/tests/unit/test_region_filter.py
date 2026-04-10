from __future__ import annotations

from pathlib import Path

from app.chat.admissions_files import (
    AdmissionsFileCandidate,
    filter_admissions_files,
    normalize_region_tokens,
)
from app.region_hints import (
    build_region_match_blob,
    infer_region_token_from_path,
    normalize_catalog_region_label,
    squash_admin_region_names,
)


def test_normalize_catalog_region_label_gyeongsang() -> None:
    assert normalize_catalog_region_label("경상북도") == "경북"
    assert normalize_catalog_region_label("경상남도") == "경남"
    assert "경북" in squash_admin_region_names("경상북도 구미시")


def test_infer_region_from_sigungu_folder() -> None:
    assert infer_region_token_from_path(r"경산시\대구대학교\수시.xlsx", "대구대학교") == "경북"


def test_infer_region_yeongnam_macro_path() -> None:
    assert (
        infer_region_token_from_path(
            r"영남권\경북\구미시\국립금오공과대학교\입시결과.xlsx",
            "국립금오공과대학교",
        )
        == "경북"
    )


def test_build_region_match_blob_for_yeongnam_filter() -> None:
    blob = build_region_match_blob(
        "경상북도",
        r"구미시\국립금오공과대학교\2025_입시결과.xlsx",
        "국립금오공과대학교",
    )
    assert "경북" in blob


def test_normalize_region_tokens_yeongnam_expansion() -> None:
    assert set(normalize_region_tokens("영남권")) == {"부산", "대구", "울산", "경북", "경남"}


def test_filter_admissions_files_yeongnam_includes_gumi_without_gyeongbuk_in_filename() -> None:
    candidates = [
        AdmissionsFileCandidate(
            path=Path("x"),
            source_path=r"구미시\국립금오공과대학교\2025_입시결과.xlsx",
            title="2025_입시결과",
            kind="result",
            school_name="국립금오공과대학교",
            region=None,
        ),
        AdmissionsFileCandidate(
            path=Path("y"),
            source_path=r"경기대학교\2025_모집결과.xlsx",
            title="2025_모집결과",
            kind="result",
            school_name="경기대학교",
            region="경기",
        ),
    ]
    out = filter_admissions_files(candidates, region_text="영남권", question_text=None)
    assert len(out) == 1
    assert "구미시" in out[0].source_path


def test_filter_admissions_files_strict_empty_when_no_match() -> None:
    candidates = [
        AdmissionsFileCandidate(
            path=Path("y"),
            source_path=r"경기대학교\2025_모집결과.xlsx",
            title="2025_모집결과",
            kind="result",
            school_name="경기대학교",
            region="경기",
        ),
    ]
    out = filter_admissions_files(candidates, region_text="영남권", question_text=None)
    assert out == []
