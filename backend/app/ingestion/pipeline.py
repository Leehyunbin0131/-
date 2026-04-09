from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd

from app.catalog.manifest import ManifestStore
from app.catalog.models import CatalogState, DatasetRecord, LineageRecord, SnapshotRecord, TableRecord
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
    REGION_KEYWORDS = (
        "서울",
        "경기",
        "인천",
        "강원",
        "대전",
        "세종",
        "충북",
        "충남",
        "대구",
        "경북",
        "부산",
        "울산",
        "경남",
        "광주",
        "전북",
        "전남",
        "제주",
    )

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

        self._refresh_dataset_regions()

        return IngestionReport(
            scanned_files=len(sources),
            ingested_files=ingested_files,
            skipped_files=skipped_files,
            table_count=total_tables,
            items=items,
        )

    @staticmethod
    def _infer_document_type(relative_path: Path) -> str | None:
        text = " ".join(relative_path.parts)
        if any(
            token in text
            for token in (
                "모집결과",
                "전형결과",
                "입시결과",
                "충원합격",
                "충원현황",
                "최초합격",
                "합격현황",
                "합격자현황",
                "경쟁률",
            )
        ):
            return "result"
        if "모집요강" in text or "요강" in text:
            return "guide"
        # 파일명 힌트가 없어도 Data 아래 스프레드시트는 file inputs 후보로 쓴다.
        return "result"

    @staticmethod
    def _extract_school_name(relative_path: Path) -> str | None:
        text = " ".join(relative_path.parts)
        matches = set(re.findall(r"([가-힣A-Za-z0-9]+대학교|[가-힣A-Za-z0-9]+대)", text))
        cleaned = [item for item in matches if item not in {"대학", "대학교"}]
        if not cleaned:
            return None
        return sorted(cleaned, key=len, reverse=True)[0]

    def _infer_region(self, relative_path: Path, school_name: str | None) -> str | None:
        text = " ".join(relative_path.parts)
        for keyword in self.REGION_KEYWORDS:
            if keyword in (school_name or "") or keyword in text:
                return keyword
        return None

    def _build_school_region_map(self, catalog: CatalogState) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for table in catalog.tables.values():
            joined = f"{table.title} {table.source_path}"
            if "학교명" not in joined and "대학현황지표" not in joined and "전국대학별학과정보표준데이터" not in joined:
                continue
            parquet_path = Path(table.parquet_path)
            if not parquet_path.exists():
                continue
            try:
                frame = pd.read_parquet(parquet_path)
            except Exception:
                continue
            school_col = next((col for col in frame.columns if "학교명" in str(col)), None)
            region_col = next(
                (col for col in frame.columns if any(token in str(col) for token in ("시도명", "지역", "소재지"))),
                None,
            )
            if school_col is None or region_col is None:
                continue
            for _, row in frame[[school_col, region_col]].dropna().iterrows():
                school = str(row[school_col]).strip()
                region = str(row[region_col]).strip()
                if school and region and school not in mapping:
                    mapping[school] = region
        return mapping

    def _refresh_dataset_regions(self) -> None:
        catalog = self.manifest_store.load()
        school_region_map = self._build_school_region_map(catalog)
        changed = False
        for dataset in catalog.datasets.values():
            if dataset.school_name and dataset.school_name in school_region_map:
                region = school_region_map[dataset.school_name]
                if dataset.region != region:
                    dataset.region = region
                    changed = True
        if changed:
            self.manifest_store.save(catalog)

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

        school_name = self._extract_school_name(relative_path)
        dataset = DatasetRecord(
            dataset_id=dataset_id,
            title=relative_path.stem,
            source_path=str(relative_path),
            topic=dataset_topic_from_path(relative_path),
            school_name=school_name,
            region=self._infer_region(relative_path, school_name),
            year=snapshot_date,
            document_type=self._infer_document_type(relative_path),
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
