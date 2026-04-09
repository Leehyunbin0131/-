from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel

from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile


class FakeEmbeddingProvider(LLMProvider):
    def __init__(self) -> None:
        self.profile = ModelProfile(
            provider="fake",
            chat_model="fake-chat",
            embedding_model="fake-embed",
            supports_tools=False,
            supports_structured_output=False,
        )

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        tools=None,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        return GenerationResponse(
            provider=self.profile.provider,
            model=model or self.profile.chat_model,
            content="",
        )

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "employment" in lowered else 0.0,
                    1.0 if "region" in lowered or "seoul" in lowered else 0.0,
                    float(len(text) % 10),
                ]
            )
        return EmbeddingResponse(
            provider=self.profile.provider,
            model=model or self.profile.embedding_model or "fake-embed",
            dimensions=3,
            vectors=vectors,
        )


def test_vector_index_and_sql_runner(container) -> None:
    container.ingestion_pipeline.run()
    provider = FakeEmbeddingProvider()
    catalog = container.manifest_store.load()
    manifest = container.vector_index.rebuild(provider, catalog)

    assert manifest.dimension == 3
    hits = container.vector_index.search(provider, "employment rate in Seoul", top_k=1)
    assert hits

    top_hit = hits[0]
    description = container.query_runner.describe_table(top_hit.doc_id)
    assert "columns" in description

    preview = container.query_runner.preview_table(top_hit.doc_id, limit=2)
    assert len(preview.rows) == 2
