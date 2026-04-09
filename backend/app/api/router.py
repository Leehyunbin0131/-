from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.catalog import router as catalog_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(catalog_router, prefix="/api/v1/catalog", tags=["catalog"])
api_router.include_router(ingestion_router, prefix="/api/v1/ingestion", tags=["ingestion"])
api_router.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
