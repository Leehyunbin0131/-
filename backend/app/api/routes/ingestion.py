from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import ServiceContainer, get_container

router = APIRouter()

@router.post("/run")
def run_ingestion(
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    try:
        report = container.ingestion_pipeline.run()
        return {
            "scanned_files": report.scanned_files,
            "ingested_files": report.ingested_files,
            "skipped_files": report.skipped_files,
            "table_count": report.table_count,
            "items": [asdict(item) for item in report.items],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
