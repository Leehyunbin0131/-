from __future__ import annotations

import json
from pathlib import Path

from app.catalog.models import (
    CatalogState,
    ColumnRecord,
    DatasetRecord,
    LineageRecord,
    SnapshotRecord,
    TableRecord,
    utc_now,
)


class ManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> CatalogState:
        if not self.path.exists():
            return CatalogState()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return CatalogState.model_validate(raw)

    def save(self, state: CatalogState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def has_file_hash(self, file_hash: str) -> bool:
        return file_hash in self.load().referenced_file_hashes()

    def has_ingested_snapshot(
        self,
        *,
        file_hash: str,
        parser_name: str,
        parser_version: str,
    ) -> bool:
        state = self.load()
        for snapshot in state.snapshots.values():
            if (
                snapshot.file_hash == file_hash
                and snapshot.parser_name == parser_name
                and snapshot.parser_version == parser_version
            ):
                return True
        return False

    def upsert_records(
        self,
        *,
        dataset: DatasetRecord,
        tables: list[TableRecord],
        columns: dict[str, list[ColumnRecord]],
        snapshot: SnapshotRecord,
        lineage: list[LineageRecord],
    ) -> CatalogState:
        state = self.load()
        dataset.updated_at = utc_now()
        dataset.latest_snapshot = snapshot.snapshot_date or snapshot.snapshot_id
        state.datasets[dataset.dataset_id] = dataset
        state.snapshots[snapshot.snapshot_id] = snapshot

        for table in tables:
            table.updated_at = utc_now()
            state.tables[table.table_id] = table

        for table_id, table_columns in columns.items():
            state.columns[table_id] = table_columns

        existing_ids = {entry.lineage_id for entry in state.lineage}
        for entry in lineage:
            if entry.lineage_id not in existing_ids:
                state.lineage.append(entry)

        self.save(state)
        return state

    def list_datasets(self) -> list[DatasetRecord]:
        return list(self.load().datasets.values())

    def list_tables(self, dataset_id: str | None = None) -> list[TableRecord]:
        tables = list(self.load().tables.values())
        if dataset_id is None:
            return tables
        return [table for table in tables if table.dataset_id == dataset_id]
