from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.catalog.models import ColumnRecord, DatasetRecord
from app.ingestion.parser_utils import infer_semantic_role, normalize_sheet_dataframe, slugify


@dataclass(slots=True)
class ParsedTable:
    table_id: str
    title: str
    sheet_name: str
    dataframe: pd.DataFrame
    columns: list[ColumnRecord]
    description: str | None = None
    grain: list[str] | None = None
    dimensions: list[str] | None = None


@dataclass(slots=True)
class ParsedDataset:
    dataset: DatasetRecord
    tables: list[ParsedTable]
    snapshot_date: str | None
    parser_name: str
    parser_version: str


class DataParser(ABC):
    extensions: tuple[str, ...] = ()
    parser_name: str = "base"
    parser_version: str = "1.0"

    @abstractmethod
    def parse(self, source_path: Path, dataset: DatasetRecord, snapshot_date: str | None) -> ParsedDataset:
        raise NotImplementedError


class BaseExcelParser(DataParser):
    engine: str | None = None

    def parse(self, source_path: Path, dataset: DatasetRecord, snapshot_date: str | None) -> ParsedDataset:
        workbook = pd.read_excel(
            source_path,
            sheet_name=None,
            header=None,
            engine=self.engine,
        )

        tables: list[ParsedTable] = []
        for sheet_name, frame in workbook.items():
            normalized = normalize_sheet_dataframe(frame)
            if normalized.empty:
                continue

            table_id = f"{dataset.dataset_id}__{slugify(sheet_name, prefix='sheet')}"
            columns: list[ColumnRecord] = []
            grain: list[str] = []
            dimensions: list[str] = []
            original_labels = normalized.attrs.get("original_column_labels", {})
            for column_name, dtype in normalized.dtypes.astype(str).items():
                display_name = original_labels.get(column_name, column_name)
                semantic_role = infer_semantic_role(display_name, dtype)
                if semantic_role in {"year", "region", "school", "major"}:
                    dimensions.append(display_name)
                if semantic_role == "metric":
                    grain.append(display_name)
                columns.append(
                    ColumnRecord(
                        column_id=f"{table_id}:{column_name}",
                        table_id=table_id,
                        name=display_name,
                        normalized_name=column_name,
                        dtype=dtype,
                        semantic_role=semantic_role,
                        description=f"Original header: {display_name}",
                    )
                )

            tables.append(
                ParsedTable(
                    table_id=table_id,
                    title=f"{dataset.title} / {sheet_name}",
                    sheet_name=sheet_name,
                    dataframe=normalized,
                    columns=columns,
                    description=f"Normalized sheet {sheet_name} from {source_path.name}",
                    grain=grain,
                    dimensions=dimensions,
                )
            )

        return ParsedDataset(
            dataset=dataset,
            tables=tables,
            snapshot_date=snapshot_date,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
        )
