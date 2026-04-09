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
    data_dir = tmp_path / "Data" / "education"
    data_dir.mkdir(parents=True, exist_ok=True)

    employment = pd.DataFrame(
        [
            {"year": 2024, "region": "Seoul", "school_type": "university", "employment_rate": 72.5, "admission_rate": 61.2},
            {"year": 2024, "region": "Busan", "school_type": "university", "employment_rate": 65.1, "admission_rate": 54.8},
            {"year": 2024, "region": "Daegu", "school_type": "college", "employment_rate": 69.9, "admission_rate": 49.4},
        ]
    )
    major = pd.DataFrame(
        [
            {"year": 2024, "major": "computer_science", "employment_rate": 78.1},
            {"year": 2024, "major": "nursing", "employment_rate": 82.4},
        ]
    )

    workbook_path = data_dir / "sample_stats_2024.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        employment.to_excel(writer, sheet_name="employment", index=False)
        major.to_excel(writer, sheet_name="major_stats", index=False)
    return tmp_path


@pytest.fixture()
def settings(workspace: Path) -> Settings:
    settings = Settings(
        project_root=workspace,
        data_root=workspace / "Data",
        storage_root=workspace / "storage",
        default_llm_provider="openai",
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
