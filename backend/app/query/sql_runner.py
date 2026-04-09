from __future__ import annotations

from typing import Any, Literal

import duckdb
from pydantic import BaseModel, Field

from app.catalog.manifest import ManifestStore
from app.catalog.models import ColumnRecord, TableRecord
from app.config import Settings


class StructuredFilter(BaseModel):
    column: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "contains"] = "="
    value: Any


class AggregateSpec(BaseModel):
    column: str
    function: Literal["avg", "sum", "min", "max", "count"] = "avg"
    alias: str | None = None


class StructuredQuery(BaseModel):
    table_id: str
    select: list[str] = Field(default_factory=list)
    filters: list[StructuredFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[AggregateSpec] = Field(default_factory=list)
    order_by: list[str] = Field(default_factory=list)
    limit: int = 20


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]


class DuckDBQueryRunner:
    def __init__(self, settings: Settings, manifest_store: ManifestStore) -> None:
        self.settings = settings
        self.manifest_store = manifest_store

    def _connect(self) -> duckdb.DuckDBPyConnection:
        self.settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.settings.duckdb_path))

    def _table_record(self, table_id: str) -> TableRecord:
        state = self.manifest_store.load()
        table = state.find_table(table_id)
        if table is None:
            raise ValueError(f"Unknown table_id: {table_id}")
        return table

    def _table_columns(self, table_id: str) -> list[ColumnRecord]:
        state = self.manifest_store.load()
        columns = state.table_columns(table_id)
        if not columns:
            raise ValueError(f"No columns registered for table_id: {table_id}")
        return columns

    def describe_table(self, table_id: str) -> dict[str, Any]:
        table = self._table_record(table_id)
        columns = self._table_columns(table_id)
        return {
            "table_id": table.table_id,
            "dataset_id": table.dataset_id,
            "title": table.title,
            "snapshot_date": table.snapshot_date,
            "row_count": table.row_count,
            "dimensions": table.dimensions,
            "grain": table.grain,
            "columns": [column.model_dump() for column in columns],
        }

    def preview_table(self, table_id: str, limit: int = 5) -> QueryResult:
        query = StructuredQuery(table_id=table_id, limit=limit)
        return self.run_structured_query(query)

    def run_structured_query(self, query: StructuredQuery) -> QueryResult:
        table = self._table_record(query.table_id)
        columns = self._table_columns(query.table_id)
        column_lookup: dict[str, str] = {}
        for column in columns:
            column_lookup[column.normalized_name] = column.normalized_name
            column_lookup[column.name] = column.normalized_name
        allowed_columns = set(column_lookup)

        select_parts: list[str] = []
        if query.select:
            for column in query.select:
                if column not in allowed_columns:
                    raise ValueError(f"Unknown select column: {column}")
                select_parts.append(f'"{column_lookup[column]}"')
        elif query.aggregates:
            select_parts = []
        else:
            select_parts.append("*")

        for aggregate in query.aggregates:
            if aggregate.column != "*" and aggregate.column not in allowed_columns:
                raise ValueError(f"Unknown aggregate column: {aggregate.column}")
            target = "*" if aggregate.column == "*" else f'"{column_lookup[aggregate.column]}"'
            alias = aggregate.alias or f"{aggregate.function}_{aggregate.column.replace('*', 'rows')}"
            select_parts.append(f"{aggregate.function.upper()}({target}) AS \"{alias}\"")

        for group_column in query.group_by:
            if group_column not in allowed_columns:
                raise ValueError(f"Unknown group_by column: {group_column}")
            normalized_group = column_lookup[group_column]
            if f'"{normalized_group}"' not in select_parts and "*" not in select_parts:
                select_parts.insert(0, f'"{normalized_group}"')

        where_clauses: list[str] = []
        parameters: list[Any] = []
        for filter_item in query.filters:
            if filter_item.column not in allowed_columns:
                raise ValueError(f"Unknown filter column: {filter_item.column}")
            normalized_filter = column_lookup[filter_item.column]
            if filter_item.operator == "contains":
                where_clauses.append(f'CAST("{normalized_filter}" AS VARCHAR) ILIKE ?')
                parameters.append(f"%{filter_item.value}%")
            else:
                where_clauses.append(f'"{normalized_filter}" {filter_item.operator} ?')
                parameters.append(filter_item.value)

        sql_parts = [f"SELECT {', '.join(select_parts)}"]
        sql_parts.append(f"FROM read_parquet('{table.parquet_path.replace('\\', '/')}')")
        if where_clauses:
            sql_parts.append(f"WHERE {' AND '.join(where_clauses)}")
        if query.group_by:
            groups = ", ".join(f'"{column_lookup[column]}"' for column in query.group_by)
            sql_parts.append(f"GROUP BY {groups}")
        if query.order_by:
            order_parts: list[str] = []
            for order_column in query.order_by:
                direction = "ASC"
                name = order_column
                if order_column.startswith("-"):
                    name = order_column[1:]
                    direction = "DESC"
                if name not in allowed_columns and name not in {
                    aggregate.alias or f"{aggregate.function}_{aggregate.column.replace('*', 'rows')}"
                    for aggregate in query.aggregates
                }:
                    raise ValueError(f"Unknown order_by column: {order_column}")
                order_identifier = column_lookup.get(name, name)
                order_parts.append(f'"{order_identifier}" {direction}')
            sql_parts.append(f"ORDER BY {', '.join(order_parts)}")
        sql_parts.append(f"LIMIT {max(1, min(query.limit, 200))}")

        sql = "\n".join(sql_parts)
        with self._connect() as connection:
            cursor = connection.execute(sql, parameters)
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
        payload_rows = [dict(zip(column_names, row, strict=True)) for row in rows]
        return QueryResult(sql=sql, columns=column_names, rows=payload_rows)
