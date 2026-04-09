from __future__ import annotations

from pathlib import Path


def test_ingestion_creates_manifest_and_parquet(container, settings) -> None:
    report = container.ingestion_pipeline.run()

    assert report.ingested_files == 1
    assert report.table_count == 2
    assert settings.catalog_path.exists()

    manifest = container.manifest_store.load()
    assert len(manifest.datasets) == 1
    assert len(manifest.tables) == 2
    assert len(manifest.snapshots) == 1

    parquet_paths = [Path(table.parquet_path) for table in manifest.tables.values()]
    assert all(path.exists() for path in parquet_paths)
