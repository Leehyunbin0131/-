from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.providers import OllamaProvider, OpenAIProvider


class ProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, provider_name: str | None = None) -> LLMProvider:
        resolved = (provider_name or self.settings.default_llm_provider).lower()
        if resolved == "openai":
            return OpenAIProvider(
                api_key=self.settings.openai_api_key,
                chat_model=self.settings.openai_chat_model,
                embedding_model=self.settings.openai_embedding_model,
                timeout_seconds=self.settings.request_timeout_seconds,
            )
        if resolved == "ollama":
            return OllamaProvider(
                base_url=self.settings.ollama_base_url,
                chat_model=self.settings.ollama_chat_model,
                embedding_model=self.settings.ollama_embedding_model,
                timeout_seconds=self.settings.request_timeout_seconds,
            )
        raise ValueError(f"Unsupported provider: {resolved}")
