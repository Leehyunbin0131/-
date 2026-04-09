from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Sequence

import ollama
from pydantic import BaseModel

from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """로컬 Ollama HTTP API. 엑셀 file input·호스팅 웹검색은 지원하지 않습니다."""

    def __init__(
        self,
        *,
        chat_model: str,
        embed_model: str,
        host: str | None = None,
        timeout_seconds: float = 300.0,
        chat_temperature: float = 0.2,
    ) -> None:
        self._chat_model = chat_model.strip()
        self._embed_model = embed_model.strip()
        self._chat_temperature = float(chat_temperature)
        client_kwargs: dict[str, Any] = {}
        if host is not None and str(host).strip():
            client_kwargs["host"] = str(host).strip().rstrip("/")
        if timeout_seconds > 0:
            client_kwargs["timeout"] = timeout_seconds
        self._client = ollama.Client(**client_kwargs)
        self.profile = ModelProfile(
            provider="ollama",
            chat_model=self._chat_model,
            embedding_model=self._embed_model,
            supports_tools=False,
            supports_structured_output=True,
        )

    @staticmethod
    def _to_ollama_messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def responses_parse(
        self,
        messages: Sequence[ChatMessage],
        *,
        text_format: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
        use_web_search: bool = False,
        file_paths: Sequence[Path] | None = None,
        use_reasoning: bool = True,
    ) -> GenerationResponse:
        del use_web_search, use_reasoning
        if file_paths:
            logger.warning(
                "OllamaProvider: %d개 로컬 파일은 전송하지 않습니다(프롬프트의 selected_files 경로만 참고).",
                len(file_paths),
            )
        resolved = (model or self._chat_model).strip()
        temp = self._chat_temperature if temperature is None else float(temperature)
        omsgs = self._to_ollama_messages(messages)
        last_err: Exception | None = None
        for fmt in (text_format.model_json_schema(), "json"):
            try:
                response = self._client.chat(
                    model=resolved,
                    messages=omsgs,
                    format=fmt,
                    options={"temperature": temp},
                )
                raw = response.message.content or ""
                data = json.loads(raw)
                obj = text_format.model_validate(data)
                return GenerationResponse(
                    provider=self.profile.provider,
                    model=resolved,
                    content=raw,
                    parsed=obj.model_dump(mode="json"),
                    tool_calls=[],
                    used_web_search=False,
                    used_file_input=False,
                    file_ids=[],
                    file_count=0,
                )
            except Exception as exc:
                last_err = exc
                logger.debug("ollama responses_parse retry: %s", exc)
                continue
        raise last_err or RuntimeError("Ollama structured chat failed")

    def responses_create(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        use_web_search: bool = False,
        file_paths: Sequence[Path] | None = None,
    ) -> GenerationResponse:
        del use_web_search
        if file_paths:
            logger.warning(
                "OllamaProvider: 후속 답변에서 %d개 파일 경로는 전송하지 않습니다.",
                len(file_paths),
            )
        resolved = (model or self._chat_model).strip()
        temp = self._chat_temperature if temperature is None else float(temperature)
        response = self._client.chat(
            model=resolved,
            messages=self._to_ollama_messages(messages),
            options={"temperature": temp},
        )
        text = (response.message.content or "").strip()
        return GenerationResponse(
            provider=self.profile.provider,
            model=resolved,
            content=text,
            parsed=None,
            tool_calls=[],
            used_web_search=False,
            used_file_input=False,
            file_ids=[],
            file_count=0,
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
        if tools:
            logger.warning("OllamaProvider: tools 인자는 무시됩니다.")
        resolved = (model or self._chat_model).strip()
        omsgs = self._to_ollama_messages(messages)
        if response_model is None:
            response = self._client.chat(
                model=resolved,
                messages=omsgs,
                options={"temperature": temperature},
            )
            return GenerationResponse(
                provider=self.profile.provider,
                model=resolved,
                content=response.message.content or "",
                parsed=None,
                tool_calls=[],
                used_web_search=False,
                used_file_input=False,
                file_ids=[],
                file_count=0,
            )

        last_err: Exception | None = None
        for fmt in (response_model.model_json_schema(), "json"):
            try:
                response = self._client.chat(
                    model=resolved,
                    messages=omsgs,
                    format=fmt,
                    options={"temperature": temperature},
                )
                raw = response.message.content or ""
                data = json.loads(raw)
                obj = response_model.model_validate(data)
                return GenerationResponse(
                    provider=self.profile.provider,
                    model=resolved,
                    content=raw,
                    parsed=obj.model_dump(mode="json"),
                    tool_calls=[],
                    used_web_search=False,
                    used_file_input=False,
                    file_ids=[],
                    file_count=0,
                )
            except Exception as exc:
                last_err = exc
                logger.debug("ollama generate structured retry: %s", exc)
                continue
        raise last_err or RuntimeError("Ollama generate with structured output failed")

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        resolved = (model or self._embed_model).strip()
        response = self._client.embed(
            model=resolved,
            input=list(texts),
            dimensions=dimensions,
        )
        vectors = list(response.embeddings)
        vector_dimensions = len(vectors[0]) if vectors else (dimensions or 0)
        return EmbeddingResponse(
            provider=self.profile.provider,
            model=resolved,
            dimensions=vector_dimensions,
            vectors=vectors,
        )
