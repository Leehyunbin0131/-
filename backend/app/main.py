from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.llm.ollama_util import ollama_base_url_for_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    name = (settings.llm_provider or "").strip().lower()
    if name in ("ollama", "local"):
        base = ollama_base_url_for_settings(settings)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base}/api/tags", timeout=2.0)
                response.raise_for_status()
        except Exception:
            logger.warning(
                "Ollama를 사용하도록 설정됐지만 %s 에 연결되지 않았습니다. "
                "Windows에서는 Ollama 데스크톱 앱을 실행해 시스템 트레이에 떠 있는지 확인하거나, "
                "터미널에서 `ollama serve` 를 띄운 뒤 브라우저로 %s/api/tags 가 열리는지 확인하세요. "
                "다른 PC의 Ollama를 쓰는 경우 COUNSEL_OLLAMA_HOST 를 그 주소로 맞추세요.",
                base,
                base,
            )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=_lifespan,
    )
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
