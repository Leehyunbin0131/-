from __future__ import annotations

from typing import Any, Sequence

from openai import OpenAI
from pydantic import BaseModel

from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self.profile = ModelProfile(
            provider="openai",
            chat_model=chat_model,
            embedding_model=embedding_model,
            supports_tools=True,
            supports_structured_output=True,
        )

    def _client(self) -> OpenAI:
        if not self._api_key:
            raise RuntimeError("COUNSEL_OPENAI_API_KEY is not configured.")
        return OpenAI(api_key=self._api_key, timeout=self._timeout_seconds)

    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        client = self._client()
        resolved_model = model or self.profile.chat_model
        payload_messages = [message.model_dump() for message in messages]

        if response_model is not None:
            completion = client.chat.completions.parse(
                model=resolved_model,
                messages=payload_messages,
                response_format=response_model,
                temperature=temperature,
            )
            message = completion.choices[0].message
            parsed = message.parsed.model_dump() if message.parsed is not None else None
            content = message.content or ""
            if parsed is not None and not content:
                content = response_model.model_validate(parsed).model_dump_json()
            return GenerationResponse(
                provider=self.profile.provider,
                model=resolved_model,
                content=content,
                parsed=parsed,
                tool_calls=[],
            )

        completion = client.chat.completions.create(
            model=resolved_model,
            messages=payload_messages,
            tools=list(tools) if tools else None,
            temperature=temperature,
        )
        message = completion.choices[0].message
        tool_calls = []
        if message.tool_calls:
            tool_calls = [tool_call.model_dump(mode="json") for tool_call in message.tool_calls]
        return GenerationResponse(
            provider=self.profile.provider,
            model=resolved_model,
            content=message.content or "",
            parsed=None,
            tool_calls=tool_calls,
        )

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        client = self._client()
        resolved_model = model or self.profile.embedding_model
        response = client.embeddings.create(
            model=resolved_model,
            input=list(texts),
            dimensions=dimensions,
        )
        vectors = [item.embedding for item in response.data]
        vector_dimensions = len(vectors[0]) if vectors else (dimensions or 0)
        return EmbeddingResponse(
            provider=self.profile.provider,
            model=resolved_model,
            dimensions=vector_dimensions,
            vectors=vectors,
        )
