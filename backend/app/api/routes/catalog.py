from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import ServiceContainer, get_container

router = APIRouter()


@router.get("/datasets")
def list_datasets(container: ServiceContainer = Depends(get_container)) -> dict[str, object]:
    datasets = [item.model_dump(mode="json") for item in container.manifest_store.list_datasets()]
    return {"items": datasets, "count": len(datasets)}


@router.get("/tables")
def list_tables(
    dataset_id: str | None = None,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    tables = [item.model_dump(mode="json") for item in container.manifest_store.list_tables(dataset_id)]
    return {"items": tables, "count": len(tables)}
