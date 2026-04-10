from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import ServiceContainer, get_container
from app.main import create_app


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    admissions_root = tmp_path / "Data" / "대학별모집결과"
    admissions_root.mkdir(parents=True, exist_ok=True)

    kyonggi_result = pd.DataFrame(
        [
            {
                "학교명": "경기대학교",
                "학과명": "컴퓨터공학부",
                "전형명": "학생부교과",
                "경쟁률": 7.1,
                "학생부등급평균": 3.4,
                "학생부등급85컷": 3.8,
            },
            {
                "학교명": "경기대학교",
                "학과명": "인공지능전공",
                "전형명": "학생부종합",
                "경쟁률": 9.3,
                "학생부등급평균": 3.6,
                "학생부등급85컷": 4.0,
            },
        ]
    )
    daegu_result = pd.DataFrame(
        [
            {
                "학교명": "대구대학교",
                "학과명": "사이버보안학과",
                "전형명": "학생부교과",
                "경쟁률": 5.2,
                "학생부등급평균": 3.9,
                "학생부등급85컷": 4.4,
            },
            {
                "학교명": "대구대학교",
                "학과명": "컴퓨터정보공학부",
                "전형명": "정시 일반",
                "경쟁률": 4.1,
                "환산점수": 520.3,
            },
        ]
    )

    kyonggi_dir = admissions_root / "경기대학교"
    kyonggi_dir.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(kyonggi_dir / "2025_모집결과.xlsx", engine="openpyxl") as writer:
        kyonggi_result.to_excel(writer, sheet_name="모집결과", index=False)

    daegu_dir = admissions_root / "대구대학교"
    daegu_dir.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(daegu_dir / "2025_모집결과.xlsx", engine="openpyxl") as writer:
        daegu_result.to_excel(writer, sheet_name="모집결과", index=False)

    mapping_dir = tmp_path / "Data" / "대학현황지표"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    mapping = pd.DataFrame(
        [
            {"학교명": "경기대학교", "시도명": "경기"},
            {"학교명": "대구대학교", "시도명": "대구"},
        ]
    )
    with pd.ExcelWriter(mapping_dir / "전국대학별학과정보표준데이터-20260409.xlsx", engine="openpyxl") as writer:
        mapping.to_excel(writer, sheet_name="Sheet1", index=False)

    return tmp_path


@pytest.fixture()
def settings(workspace: Path) -> Settings:
    settings = Settings(
        project_root=workspace,
        data_root=workspace / "Data",
        storage_root=workspace / "storage",
    )
    settings.ensure_storage_dirs()
    return settings


@pytest.fixture()
def container(settings: Settings) -> ServiceContainer:
    return ServiceContainer(settings)


@pytest.fixture()
def client(settings: Settings, container: ServiceContainer) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_container] = lambda: container
    return TestClient(app)
