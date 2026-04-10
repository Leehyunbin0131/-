from __future__ import annotations

from pathlib import Path

from app.catalog.models import CatalogState
from app.chat.admissions_files import (
    AdmissionsFileCandidate,
    _candidate_kind,
    dedupe_prefer_structured_over_pdf,
    is_llm_admissions_path,
    list_admissions_files,
    structured_input_tier,
)
from app.config import Settings


def test_candidate_kind_pdf_with_ipsi() -> None:
    assert _candidate_kind(r"경산시\경일대학교\2025학년도 수시모집 입시결과.pdf") == "result"


def test_structured_input_tier() -> None:
    assert structured_input_tier(Path("a.xlsx")) == 0
    assert structured_input_tier(Path("b.pdf")) == 1


def test_is_llm_admissions_path() -> None:
    assert is_llm_admissions_path(Path("x.pdf")) is True
    assert is_llm_admissions_path(Path("x.png")) is False


def test_dedupe_drops_pdf_when_xlsx_same_bucket(tmp_path: Path) -> None:
    a = AdmissionsFileCandidate(
        path=Path("x.xlsx"),
        source_path=r"영남권\경북\경산시\가톨릭대\2025학년도 수시모집 입시결과.xlsx",
        title="t",
        kind="result",
        school_name="가톨릭대학교",
    )
    b = AdmissionsFileCandidate(
        path=Path("y.pdf"),
        source_path=r"영남권\경북\경산시\가톨릭대\2025학년도 수시모집 입시결과.pdf",
        title="t",
        kind="result",
        school_name="가톨릭대학교",
    )
    out = dedupe_prefer_structured_over_pdf([a, b])
    assert len(out) == 1
    assert out[0].path.suffix == ".xlsx"


def test_dedupe_keeps_pdf_only_school(tmp_path: Path) -> None:
    pdf_only = AdmissionsFileCandidate(
        path=Path("y.pdf"),
        source_path=r"영남권\경북\김천시\김천대학교\2025학년도+수시정시+결과(고등학교).pdf",
        title="t",
        kind="result",
        school_name="김천대학교",
    )
    out = dedupe_prefer_structured_over_pdf([pdf_only])
    assert len(out) == 1


def test_list_admissions_files_includes_pdf(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    school = data / "영남권" / "경북" / "시험시" / "테스트대학교"
    school.mkdir(parents=True)
    (school / "2025_수시_입시결과.pdf").write_bytes(b"%PDF-1.4\n")
    settings = Settings(project_root=tmp_path, data_root=data, storage_root=tmp_path / "storage")
    settings.ensure_storage_dirs()
    candidates = list_admissions_files(settings, CatalogState())
    assert any(c.path.suffix.lower() == ".pdf" for c in candidates)
