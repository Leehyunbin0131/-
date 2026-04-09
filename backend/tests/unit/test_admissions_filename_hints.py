from __future__ import annotations

from pathlib import Path

from app.catalog.models import CatalogState
from app.chat.admissions_files import _candidate_kind, list_admissions_files
from app.config import Settings


def test_candidate_kind_recognizes_daegu_chungwon_filename() -> None:
    path = r"대구대학교\대구대_2025학년도 정시 전형별 충원합격 현황.xlsx"
    assert _candidate_kind(path) == "result"


def test_candidate_kind_still_recognizes_classic_mojip_result() -> None:
    assert _candidate_kind("경기대학교\\2025_모집결과.xlsx") == "result"


def test_candidate_kind_recognizes_guide() -> None:
    assert _candidate_kind("서울대\\2025_모집요강.xlsx") == "guide"


def test_list_admissions_files_includes_any_xlsx_without_keyword(tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    folder = data_root / "대구대학교"
    folder.mkdir(parents=True)
    (folder / "무작위이름.xlsx").write_bytes(b"")

    settings = Settings(
        project_root=tmp_path,
        data_root=data_root,
        storage_root=tmp_path / "storage",
    )
    settings.ensure_storage_dirs()

    candidates = list_admissions_files(settings, CatalogState())
    assert len(candidates) == 1
    assert candidates[0].kind == "result"
    assert "무작위이름" in candidates[0].source_path
