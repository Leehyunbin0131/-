from __future__ import annotations

from app.config import Settings
from app.llm.file_cache import OpenAIFileCacheStore
from app.llm.providers import OpenAIProvider


class ProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> OpenAIProvider:
        return OpenAIProvider(
            api_key=self.settings.openai_api_key,
            chat_model=self.settings.openai_chat_model,
            embedding_model=self.settings.openai_embedding_model,
            timeout_seconds=self.settings.request_timeout_seconds,
            responses_timeout_seconds=self.settings.openai_responses_timeout_seconds,
            web_search_model=self.settings.openai_web_search_model,
            reasoning_effort=self.settings.openai_reasoning_effort,
            responses_temperature=self.settings.openai_responses_temperature,
            file_cache_store=OpenAIFileCacheStore(self.settings.openai_file_cache_path),
        )
