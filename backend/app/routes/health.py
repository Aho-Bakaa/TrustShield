"""Health / status endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..llm import llm_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "app": s.app_name,
        "llm": llm_status(),
        "render_enabled": s.render_enabled,
    }
