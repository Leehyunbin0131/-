from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from app.catalog.models import CatalogState, TableRecord
from app.ingestion.parser_utils import summarize_dataframe
from app.llm.base import LLMProvider
from app.query.sql_runner import DuckDBQueryRunner
from app.retrieval.index_manifest import IndexManifest, IndexManifestStore, IndexedDocument


class SearchHit(BaseModel):
    doc_id: str
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorIndex:
    def __init__(
        self,
        store: IndexManifestStore,
        query_runner: DuckDBQueryRunner,
    ) -> None:
        self.store = store
        self.query_runner = query_runner

    def build_documents(self, catalog: CatalogState) -> list[IndexedDocument]:
        documents: list[IndexedDocument] = []
        for dataset in catalog.datasets.values():
            for table in catalog.dataset_tables(dataset.dataset_id):
                columns = catalog.table_columns(table.table_id)
                column_summary = ", ".join(column.name for column in columns)
                text = (
                    f"dataset={dataset.title}; topic={dataset.topic}; table={table.title}; "
                    f"sheet={table.sheet_name}; columns={column_summary}; "
                    f"dimensions={', '.join(table.dimensions)}; metrics={', '.join(table.grain)}"
                )
                documents.append(
                    IndexedDocument(
                        doc_id=table.table_id,
                        text=text,
                        metadata={
                            "dataset_id": dataset.dataset_id,
                            "dataset_title": dataset.title,
                            "table_id": table.table_id,
                            "table_title": table.title,
                            "snapshot_date": table.snapshot_date,
                            "source_path": table.source_path,
                        },
                    )
                )
        return documents

    def rebuild(self, provider: LLMProvider, catalog: CatalogState) -> IndexManifest:
        documents = self.build_documents(catalog)
        if not documents:
            manifest = IndexManifest(
                embedding_provider=provider.profile.provider,
                embedding_model=provider.profile.embedding_model or "none",
                dimension=0,
                documents=[],
            )
            self.store.save(manifest)
            return manifest

        embedding_response = provider.embed(
            [document.text for document in documents],
            model=provider.profile.embedding_model,
        )
        for document, vector in zip(documents, embedding_response.vectors, strict=True):
            document.vector = vector

        manifest = IndexManifest(
            embedding_provider=embedding_response.provider,
            embedding_model=embedding_response.model,
            dimension=embedding_response.dimensions,
            documents=documents,
        )
        self.store.save(manifest)
        return manifest

    def search(
        self,
        provider: LLMProvider,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        manifest = self.store.load()
        if manifest is None or not manifest.documents:
            return []

        query_embedding = provider.embed([query], model=manifest.embedding_model, dimensions=manifest.dimension)
        query_vector = query_embedding.vectors[0]

        hits: list[SearchHit] = []
        for document in manifest.documents:
            if filters and any(document.metadata.get(key) != value for key, value in filters.items()):
                continue
            score = cosine_similarity(query_vector, document.vector)
            hits.append(
                SearchHit(
                    doc_id=document.doc_id,
                    score=score,
                    text=document.text,
                    metadata=document.metadata,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def enrich_hit_preview(self, table: TableRecord) -> str:
        preview = self.query_runner.preview_table(table.table_id, limit=3)
        return summarize_dataframe_from_rows(preview.rows)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def summarize_dataframe_from_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No preview rows available."
    return f"preview_rows={rows}"
