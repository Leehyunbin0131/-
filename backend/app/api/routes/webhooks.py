from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.dependencies import ServiceContainer, get_container

router = APIRouter()


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, str]:
    try:
        payload = await request.body()
        event_type = container.billing_service.process_webhook(
            payload=payload,
            signature=stripe_signature or "",
        )
        return {"status": "ok", "event_type": event_type}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
