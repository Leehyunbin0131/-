from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.file_cache import OpenAIFileCacheStore
from app.llm.ollama_util import ollama_base_url_for_settings
from app.llm.providers import OllamaProvider, OpenAIProvider


class ProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, provider_name: str | None = None) -> LLMProvider:
        name = (provider_name or self.settings.llm_provider or "openai").strip().lower()
        if name in ("ollama", "local"):
            return OllamaProvider(
                chat_model=self.settings.ollama_chat_model,
                embed_model=self.settings.ollama_embed_model,
                host=ollama_base_url_for_settings(self.settings),
                timeout_seconds=self.settings.ollama_timeout_seconds,
                chat_temperature=self.settings.ollama_chat_temperature,
            )
        if name in ("openai", ""):
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
        raise ValueError(
            f"Unsupported LLM provider {name!r}. Use 'openai', 'ollama', or 'local' (COUNSEL_LLM_PROVIDER)."
        )
