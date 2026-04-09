from __future__ import annotations

from dataclasses import asdict

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import ServiceContainer, get_container

router = APIRouter()


class IngestionRequest(BaseModel):
    rebuild_index: bool = False
    provider_name: str | None = None


@router.post("/run")
def run_ingestion(
    payload: IngestionRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    report = container.ingestion_pipeline.run()
    response: dict[str, object] = {
        "scanned_files": report.scanned_files,
        "ingested_files": report.ingested_files,
        "skipped_files": report.skipped_files,
        "table_count": report.table_count,
        "items": [asdict(item) for item in report.items],
    }
    if payload.rebuild_index:
        try:
            response["index"] = container.rebuild_index(payload.provider_name)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return response
