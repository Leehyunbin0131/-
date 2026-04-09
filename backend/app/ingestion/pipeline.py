from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.catalog.manifest import ManifestStore
from app.catalog.models import DatasetRecord, LineageRecord, SnapshotRecord, TableRecord
from app.config import Settings
from app.ingestion.parser_utils import (
    build_dataset_id,
    dataset_topic_from_path,
    extract_snapshot_date,
    hash_file,
    prepare_for_parquet,
)
from app.ingestion.registry import ParserRegistry


@dataclass(slots=True)
class IngestedFileReport:
    source_path: str
    dataset_id: str
    snapshot_id: str
    tables_written: int
    skipped: bool = False


@dataclass(slots=True)
class IngestionReport:
    scanned_files: int
    ingested_files: int
    skipped_files: int
    table_count: int
    items: list[IngestedFileReport]


class IngestionPipeline:
    SUPPORTED_PATTERNS = ("*.xls", "*.xlsx", "*.xlsm")

    def __init__(
        self,
        settings: Settings,
        manifest_store: ManifestStore,
        parser_registry: ParserRegistry,
    ) -> None:
        self.settings = settings
        self.manifest_store = manifest_store
        self.parser_registry = parser_registry

    def scan_sources(self) -> list[Path]:
        discovered: list[Path] = []
        for pattern in self.SUPPORTED_PATTERNS:
            discovered.extend(self.settings.data_root.rglob(pattern))
        return sorted(set(discovered))

    def run(self) -> IngestionReport:
        sources = self.scan_sources()
        items: list[IngestedFileReport] = []
        ingested_files = 0
        skipped_files = 0
        total_tables = 0

        for source_path in sources:
            item = self.ingest_file(source_path)
            items.append(item)
            total_tables += item.tables_written
            if item.skipped:
                skipped_files += 1
            else:
                ingested_files += 1

        return IngestionReport(
            scanned_files=len(sources),
            ingested_files=ingested_files,
            skipped_files=skipped_files,
            table_count=total_tables,
            items=items,
        )

    def ingest_file(self, source_path: Path) -> IngestedFileReport:
        file_hash = hash_file(source_path)
        relative_path = source_path.relative_to(self.settings.data_root)
        dataset_id = build_dataset_id(relative_path)
        snapshot_date = extract_snapshot_date(source_path)
        snapshot_token = snapshot_date or "undated"
        snapshot_id = f"{dataset_id}:{snapshot_token}:{file_hash[:8]}"
        parser = self.parser_registry.get_parser(source_path)

        if self.manifest_store.has_ingested_snapshot(
            file_hash=file_hash,
            parser_name=parser.parser_name,
            parser_version=parser.parser_version,
        ):
            return IngestedFileReport(
                source_path=str(source_path),
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
                tables_written=0,
                skipped=True,
            )

        dataset = DatasetRecord(
            dataset_id=dataset_id,
            title=relative_path.stem,
            source_path=str(relative_path),
            topic=dataset_topic_from_path(relative_path),
            tags=[part for part in relative_path.parts[:-1]],
        )
        parsed_dataset = parser.parse(source_path, dataset, snapshot_date)

        table_records: list[TableRecord] = []
        column_records: dict[str, list] = {}
        lineage: list[LineageRecord] = []

        parquet_root = self.settings.storage_root / "silver" / dataset_id / snapshot_token
        parquet_root.mkdir(parents=True, exist_ok=True)

        for table in parsed_dataset.tables:
            parquet_path = parquet_root / f"{table.table_id}.parquet"
            safe_frame = prepare_for_parquet(table.dataframe)
            safe_frame.to_parquet(parquet_path, index=False)

            table_record = TableRecord(
                table_id=table.table_id,
                dataset_id=dataset_id,
                title=table.title,
                description=table.description,
                sheet_name=table.sheet_name,
                parquet_path=str(parquet_path),
                source_path=str(relative_path),
                snapshot_id=snapshot_id,
                snapshot_date=snapshot_date,
                row_count=len(safe_frame.index),
                grain=table.grain or [],
                dimensions=table.dimensions or [],
            )
            table_records.append(table_record)
            column_records[table.table_id] = table.columns
            lineage.append(
                LineageRecord(
                    lineage_id=f"{snapshot_id}:{table.table_id}",
                    dataset_id=dataset_id,
                    table_id=table.table_id,
                    snapshot_id=snapshot_id,
                    source_file=str(relative_path),
                    file_hash=file_hash,
                    parser_name=parsed_dataset.parser_name,
                    parser_version=parsed_dataset.parser_version,
                )
            )

        snapshot = SnapshotRecord(
            snapshot_id=snapshot_id,
            dataset_id=dataset_id,
            source_file=str(relative_path),
            file_hash=file_hash,
            snapshot_date=snapshot_date,
            parser_name=parsed_dataset.parser_name,
            parser_version=parsed_dataset.parser_version,
            tables=[table.table_id for table in parsed_dataset.tables],
        )

        self.manifest_store.upsert_records(
            dataset=dataset,
            tables=table_records,
            columns=column_records,
            snapshot=snapshot,
            lineage=lineage,
        )

        return IngestedFileReport(
            source_path=str(source_path),
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            tables_written=len(table_records),
        )
