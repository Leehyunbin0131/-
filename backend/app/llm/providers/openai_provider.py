from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from app.ingestion.parser_utils import hash_file
from app.llm.base import ChatMessage, EmbeddingResponse, GenerationResponse, LLMProvider, ModelProfile
from app.llm.file_cache import OpenAIFileCacheRecord, OpenAIFileCacheStore


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        chat_model: str,
        embedding_model: str,
        timeout_seconds: float = 60.0,
        responses_timeout_seconds: float = 900.0,
        web_search_model: str | None = None,
        reasoning_effort: str = "medium",
        responses_temperature: float | None = None,
        file_cache_store: OpenAIFileCacheStore | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._responses_timeout_seconds = max(30.0, float(responses_timeout_seconds))
        self._web_search_model = (web_search_model or "").strip() or None
        self._reasoning_effort = reasoning_effort.strip() if reasoning_effort else ""
        self._responses_temperature = responses_temperature
        self._file_cache_store = file_cache_store
        self.profile = ModelProfile(
            provider="openai",
            chat_model=chat_model,
            embedding_model=embedding_model,
            supports_tools=True,
            supports_structured_output=True,
        )

    def resolved_web_search_model(self) -> str:
        return self._web_search_model or self.profile.chat_model

    @staticmethod
    def messages_to_responses_input(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
        return [{"type": "message", "role": m.role, "content": m.content} for m in messages]

    @staticmethod
    def _instructions_and_user_text(messages: Sequence[ChatMessage]) -> tuple[str | None, str]:
        instructions: list[str] = []
        user_blocks: list[str] = []
        for message in messages:
            if message.role == "system":
                instructions.append(message.content)
                continue
            if len(messages) <= 2:
                user_blocks.append(message.content)
            else:
                user_blocks.append(f"[{message.role}]\n{message.content}")
        joined_user_text = "\n\n".join(block for block in user_blocks if block.strip())
        joined_instructions = "\n\n".join(block for block in instructions if block.strip()) or None
        return joined_instructions, joined_user_text

    def _reasoning_payload(self) -> dict[str, Any] | None:
        if not self._reasoning_effort:
            return None
        return {"effort": self._reasoning_effort}

    def upload_user_files(self, paths: Sequence[Path], *, client: OpenAI | None = None) -> list[str]:
        resolved = client or self._client()
        file_ids: list[str] = []
        for raw_path in paths:
            path = Path(raw_path)
            file_hash = hash_file(path)
            cached = self._file_cache_store.get(file_hash) if self._file_cache_store is not None else None
            if cached is not None:
                file_ids.append(cached.file_id)
                continue
            uploaded = resolved.files.create(file=path, purpose="user_data")
            file_ids.append(uploaded.id)
            if self._file_cache_store is not None:
                self._file_cache_store.put(
                    OpenAIFileCacheRecord(
                        file_hash=file_hash,
                        file_id=uploaded.id,
                        source_path=str(path),
                        filename=path.name,
                    )
                )
        return file_ids

    def _responses_input_with_files(
        self,
        messages: Sequence[ChatMessage],
        *,
        file_ids: Sequence[str] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        instructions, user_text = self._instructions_and_user_text(messages)
        content_parts: list[dict[str, Any]] = []
        for file_id in file_ids or []:
            content_parts.append({"type": "input_file", "file_id": file_id})
        content_parts.append({"type": "input_text", "text": user_text})
        return instructions, [{"role": "user", "content": content_parts}]

    @staticmethod
    def _responses_metadata(resp: Any) -> tuple[list[dict[str, Any]], bool]:
        """Best-effort extraction of hosted tool calls from Responses API payloads."""
        try:
            payload = resp.model_dump(mode="json")
        except Exception:
            try:
                payload = resp.model_dump()
            except Exception:
                payload = {}

        tool_calls: list[dict[str, Any]] = []
        used_web_search = False

        def visit(node: Any) -> None:
            nonlocal used_web_search
            if isinstance(node, dict):
                node_type = node.get("type")
                node_name = node.get("name")
                if (
                    isinstance(node_type, str)
                    and "web_search" in node_type
                ) or (
                    isinstance(node_name, str)
                    and "web_search" in node_name
                ):
                    used_web_search = True
                    tool_calls.append(node)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(payload)
        return tool_calls, used_web_search

    def _client(self) -> OpenAI:
        if not self._api_key:
            raise RuntimeError("COUNSEL_OPENAI_API_KEY is not configured.")
        return OpenAI(api_key=self._api_key, timeout=self._timeout_seconds)

    def _client_for_responses(self) -> OpenAI:
        """Longer timeout for Responses API and file uploads used with it."""
        if not self._api_key:
            raise RuntimeError("COUNSEL_OPENAI_API_KEY is not configured.")
        return OpenAI(api_key=self._api_key, timeout=self._responses_timeout_seconds)

    def _effective_responses_temperature(self, override: float | None) -> float | None:
        if override is not None:
            return override
        return self._responses_temperature

    @staticmethod
    def _responses_parse_maybe_retry(client: OpenAI, kwargs: dict[str, Any]) -> Any:
        try:
            return client.responses.parse(**kwargs)
        except BadRequestError as exc:
            msg = str(exc).lower()
            if (
                "temperature" in kwargs
                and "temperature" in msg
                and ("not supported" in msg or "unsupported" in msg)
            ):
                retry = {k: v for k, v in kwargs.items() if k != "temperature"}
                return client.responses.parse(**retry)
            raise

    @staticmethod
    def _responses_create_maybe_retry(client: OpenAI, kwargs: dict[str, Any]) -> Any:
        try:
            return client.responses.create(**kwargs)
        except BadRequestError as exc:
            msg = str(exc).lower()
            if (
                "temperature" in kwargs
                and "temperature" in msg
                and ("not supported" in msg or "unsupported" in msg)
            ):
                retry = {k: v for k, v in kwargs.items() if k != "temperature"}
                return client.responses.create(**retry)
            raise

    def responses_parse_with_web_search(
        self,
        messages: Sequence[ChatMessage],
        *,
        text_format: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
        file_paths: Sequence[Path] | None = None,
    ) -> GenerationResponse:
        """Responses API with hosted web_search tool + structured parse (e.g. CounselingSummary)."""
        return self.responses_parse(
            messages,
            text_format=text_format,
            model=model,
            temperature=temperature,
            use_web_search=True,
            file_paths=file_paths,
        )

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
        client = self._client_for_responses()
        resolved = model or (
            self.resolved_web_search_model() if use_web_search else self.profile.chat_model
        )
        file_ids = self.upload_user_files(file_paths or [], client=client)
        instructions, input_payload = self._responses_input_with_files(messages, file_ids=file_ids)
        kwargs: dict[str, Any] = {
            "model": resolved,
            "text_format": text_format,
            "input": input_payload,
        }
        temp = self._effective_responses_temperature(temperature)
        if temp is not None:
            kwargs["temperature"] = temp
        if instructions:
            kwargs["instructions"] = instructions
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search"}]
            kwargs["tool_choice"] = "auto"
        if use_reasoning:
            reasoning = self._reasoning_payload()
            if reasoning:
                kwargs["reasoning"] = reasoning
        resp = self._responses_parse_maybe_retry(client, kwargs)
        parsed_obj = resp.output_parsed
        parsed_dump = parsed_obj.model_dump(mode="json") if parsed_obj is not None else None
        tool_calls, used_web_search = self._responses_metadata(resp)
        return GenerationResponse(
            provider=self.profile.provider,
            model=resolved,
            content=resp.output_text or "",
            parsed=parsed_dump,
            tool_calls=tool_calls,
            used_web_search=used_web_search,
            used_file_input=bool(file_ids),
            file_ids=file_ids,
            file_count=len(file_ids),
        )

    def responses_create_with_web_search(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        file_paths: Sequence[Path] | None = None,
    ) -> GenerationResponse:
        """Responses API with hosted web_search; plain text output (e.g. follow-up)."""
        return self.responses_create(
            messages,
            model=model,
            temperature=temperature,
            use_web_search=True,
            file_paths=file_paths,
        )

    def responses_create(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        use_web_search: bool = False,
        file_paths: Sequence[Path] | None = None,
    ) -> GenerationResponse:
        client = self._client_for_responses()
        resolved = model or (
            self.resolved_web_search_model() if use_web_search else self.profile.chat_model
        )
        file_ids = self.upload_user_files(file_paths or [], client=client)
        instructions, input_payload = self._responses_input_with_files(messages, file_ids=file_ids)
        kwargs: dict[str, Any] = {
            "model": resolved,
            "input": input_payload,
        }
        temp = self._effective_responses_temperature(temperature)
        if temp is not None:
            kwargs["temperature"] = temp
        if instructions:
            kwargs["instructions"] = instructions
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search"}]
            kwargs["tool_choice"] = "auto"
        reasoning = self._reasoning_payload()
        if reasoning:
            kwargs["reasoning"] = reasoning
        resp = self._responses_create_maybe_retry(client, kwargs)
        tool_calls, used_web_search = self._responses_metadata(resp)
        return GenerationResponse(
            provider=self.profile.provider,
            model=resolved,
            content=resp.output_text or "",
            parsed=None,
            tool_calls=tool_calls,
            used_web_search=used_web_search,
            used_file_input=bool(file_ids),
            file_ids=file_ids,
            file_count=len(file_ids),
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
        client = self._client()
        resolved_model = model or self.profile.chat_model
        payload_messages = [message.model_dump() for message in messages]
        common_kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": payload_messages,
            "temperature": temperature,
        }
        if self._reasoning_effort:
            common_kwargs["reasoning_effort"] = self._reasoning_effort

        if response_model is not None:
            completion = client.chat.completions.parse(
                response_format=response_model,
                **common_kwargs,
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
                used_web_search=False,
                used_file_input=False,
                file_ids=[],
                file_count=0,
            )

        completion = client.chat.completions.create(
            tools=list(tools) if tools else None,
            **common_kwargs,
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
            used_web_search=False,
            used_file_input=False,
            file_ids=[],
            file_count=0,
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
