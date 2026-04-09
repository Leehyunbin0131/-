from __future__ import annotations

from pathlib import Path


def test_ingestion_creates_manifest_and_parquet(container, settings) -> None:
    report = container.ingestion_pipeline.run()

    assert report.ingested_files == 3
    assert report.table_count == 3
    assert settings.catalog_path.exists()

    manifest = container.manifest_store.load()
    assert len(manifest.datasets) == 3
    assert len(manifest.tables) == 3
    assert len(manifest.snapshots) == 3
    admissions_datasets = [
        dataset
        for dataset in manifest.datasets.values()
        if dataset.document_type in {"result", "guide"}
    ]
    assert admissions_datasets
    assert any(dataset.school_name == "대구대학교" for dataset in admissions_datasets)
    assert any(dataset.region for dataset in admissions_datasets)

    parquet_paths = [Path(table.parquet_path) for table in manifest.tables.values()]
    assert all(path.exists() for path in parquet_paths)
