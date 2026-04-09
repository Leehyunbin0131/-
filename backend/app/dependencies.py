from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Request

from app.audit.answer_trace import AnswerTraceStore
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.catalog.manifest import ManifestStore
from app.chat.orchestrator import CounselingOrchestrator
from app.chat.session_store import SessionStore
from app.config import Settings, get_settings
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.registry import ParserRegistry
from app.llm.factory import ProviderFactory
from app.usage.service import UsageService
from app.usage.store import UsageStore


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.manifest_store = ManifestStore(settings.catalog_path)
        self.session_store = SessionStore(settings.sessions_root)
        self.auth_store = AuthStore(settings.auth_state_path)
        self.usage_store = UsageStore(settings.usage_state_path)
        self.parser_registry = ParserRegistry.default()
        self.ingestion_pipeline = IngestionPipeline(settings, self.manifest_store, self.parser_registry)
        self.provider_factory = ProviderFactory(settings)
        self.trace_store = AnswerTraceStore(settings.answer_trace_path)
        self.usage_service = UsageService(settings, self.usage_store)
        self.auth_service = AuthService(settings, self.auth_store)
        self.orchestrator = CounselingOrchestrator(
            settings=settings,
            manifest_store=self.manifest_store,
            session_store=self.session_store,
            provider_factory=self.provider_factory,
            trace_store=self.trace_store,
            usage_service=self.usage_service,
        )


@lru_cache(maxsize=1)
def get_container_cached() -> ServiceContainer:
    return ServiceContainer(get_settings())


def get_container(_: Request, settings: Settings = Depends(get_settings)) -> ServiceContainer:
    container = get_container_cached()
    if container.settings != settings:
        return ServiceContainer(settings)
    return container
