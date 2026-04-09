from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatasetRecord(BaseModel):
    dataset_id: str
    title: str
    source_path: str
    topic: str | None = None
    school_name: str | None = None
    region: str | None = None
    year: str | None = None
    document_type: str | None = None
    provider: str = "stats-data"
    source_uri: str | None = None
    license_name: str | None = None
    latest_snapshot: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TableRecord(BaseModel):
    table_id: str
    dataset_id: str
    title: str
    description: str | None = None
    sheet_name: str
    parquet_path: str
    source_path: str
    snapshot_id: str
    snapshot_date: str | None = None
    row_count: int = 0
    grain: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ColumnRecord(BaseModel):
    column_id: str
    table_id: str
    name: str
    normalized_name: str
    dtype: str
    unit: str | None = None
    description: str | None = None
    semantic_role: str | None = None


class SnapshotRecord(BaseModel):
    snapshot_id: str
    dataset_id: str
    source_file: str
    file_hash: str
    snapshot_date: str | None = None
    ingested_at: datetime = Field(default_factory=utc_now)
    parser_name: str
    parser_version: str
    tables: list[str] = Field(default_factory=list)


class LineageRecord(BaseModel):
    lineage_id: str
    dataset_id: str
    table_id: str
    snapshot_id: str
    source_file: str
    file_hash: str
    parser_name: str
    parser_version: str
    created_at: datetime = Field(default_factory=utc_now)


class CatalogState(BaseModel):
    datasets: dict[str, DatasetRecord] = Field(default_factory=dict)
    tables: dict[str, TableRecord] = Field(default_factory=dict)
    columns: dict[str, list[ColumnRecord]] = Field(default_factory=dict)
    snapshots: dict[str, SnapshotRecord] = Field(default_factory=dict)
    lineage: list[LineageRecord] = Field(default_factory=list)

    def find_table(self, table_id: str) -> TableRecord | None:
        return self.tables.get(table_id)

    def dataset_tables(self, dataset_id: str) -> list[TableRecord]:
        return [table for table in self.tables.values() if table.dataset_id == dataset_id]

    def table_columns(self, table_id: str) -> list[ColumnRecord]:
        return self.columns.get(table_id, [])

    def referenced_file_hashes(self) -> set[str]:
        return {snapshot.file_hash for snapshot in self.snapshots.values()}

    def to_public_summary(self) -> dict[str, Any]:
        return {
            "dataset_count": len(self.datasets),
            "table_count": len(self.tables),
            "snapshot_count": len(self.snapshots),
        }
