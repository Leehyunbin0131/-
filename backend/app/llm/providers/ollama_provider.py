from __future__ import annotations

import json
from typing import Any, Sequence

import httpx
from pydantic import BaseModel

from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.profile = ModelProfile(
            provider="ollama",
            chat_model=chat_model,
            embedding_model=embedding_model,
            supports_tools=True,
            supports_structured_output=True,
        )

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        resolved_model = model or self.profile.chat_model
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [message.model_dump() for message in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if response_model is not None:
            payload["format"] = response_model.model_json_schema()
        if tools:
            payload["tools"] = list(tools)

        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = client.post("/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()

        message = body.get("message", {})
        content = message.get("content", "") or ""
        parsed: Any | None = None
        if response_model is not None and content:
            try:
                parsed = response_model.model_validate_json(content).model_dump()
            except Exception:
                try:
                    parsed = response_model.model_validate(json.loads(content)).model_dump()
                except Exception:
                    parsed = None
        return GenerationResponse(
            provider=self.profile.provider,
            model=resolved_model,
            content=content,
            parsed=parsed,
            tool_calls=message.get("tool_calls", []),
        )

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        resolved_model = model or self.profile.embedding_model
        payload: dict[str, Any] = {
            "model": resolved_model,
            "input": list(texts),
            "truncate": True,
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions

        with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = client.post("/api/embed", json=payload)
            response.raise_for_status()
            body = response.json()

        vectors = body.get("embeddings", [])
        vector_dimensions = len(vectors[0]) if vectors else (dimensions or 0)
        return EmbeddingResponse(
            provider=self.profile.provider,
            model=resolved_model,
            dimensions=vector_dimensions,
            vectors=vectors,
        )
