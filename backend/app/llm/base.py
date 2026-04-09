from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ModelProfile(BaseModel):
    provider: str
    chat_model: str
    embedding_model: str | None = None
    supports_tools: bool = False
    supports_structured_output: bool = False


class GenerationResponse(BaseModel):
    provider: str
    model: str
    content: str
    parsed: Any | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    used_web_search: bool = False
    used_file_input: bool = False
    file_ids: list[str] = Field(default_factory=list)
    file_count: int = 0


class EmbeddingResponse(BaseModel):
    provider: str
    model: str
    dimensions: int
    vectors: list[list[float]]


class LLMProvider(ABC):
    profile: ModelProfile

    @property
    def supports_tools(self) -> bool:
        return self.profile.supports_tools

    @property
    def supports_structured_output(self) -> bool:
        return self.profile.supports_structured_output

    @abstractmethod
    def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        response_model: type[BaseModel] | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        raise NotImplementedError

    @abstractmethod
    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        raise NotImplementedError
