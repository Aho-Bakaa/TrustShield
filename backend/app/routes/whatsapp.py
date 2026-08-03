"""WhatsApp Cloud API webhook routes (roadmap 3.1)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from .. import whatsapp_bot
from ..log import get_logger

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
_log = get_logger("api")


@router.get("/webhook")
async def webhook_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> str:
    """Meta subscription verification handshake."""
    challenge = whatsapp_bot.verify_hub({
        "hub.mode": hub_mode or "",
        "hub.verify_token": hub_token or "",
        "hub.challenge": hub_challenge or "",
    })
    if challenge is None:
        raise HTTPException(403, "Verification token mismatch")
    return challenge


@router.post("/webhook")
async def webhook_receive(request: Request):
    """Receive a WhatsApp message, analyze it, and reply with a verdict.

    Verifies Meta's X-Hub-Signature-256 HMAC over the raw body before
    processing, so only requests genuinely signed by Meta are accepted.
    """
    if not whatsapp_bot.webhook_enabled():
        raise HTTPException(403, "WhatsApp bot not configured")

    raw = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not whatsapp_bot.verify_signature(raw, signature):
        raise HTTPException(403, "Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    status = await request.app.loop.run_in_executor(None, whatsapp_bot.handle_webhook, payload)
    if status != 200:
        raise HTTPException(status, "Webhook processing failed")
    return {"status": "ok"}


@router.post("/flush")
async def webhook_flush(request: Request):
    """Retry sending queued replies whose backoff has elapsed."""
    sent = await request.app.loop.run_in_executor(None, whatsapp_bot.flush_pending)
    return {"flushed": sent}
