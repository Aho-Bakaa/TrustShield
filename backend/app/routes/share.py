"""Shareable verdicts (roadmap 3.2).

- POST /api/share/{analysis_id} -> { token, url }  (7-day expiry)
- GET  /api/share/{token}       -> full AnalysisResult (or 404/410)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import store
from ..log import get_logger

router = APIRouter(prefix="/api/share", tags=["share"])
_log = get_logger("api")


@router.post("/{analysis_id}")
async def create_share(analysis_id: str) -> dict:
    """Create a share token for an existing analysis."""
    if not store.get(analysis_id):
        raise HTTPException(404, "Analysis not found")
    token = store.create_share_token(analysis_id)
    return {"token": token, "analysis_id": analysis_id}


@router.get("/{token}")
async def resolve_share(token: str):
    """Resolve a share token into its full analysis result."""
    analysis_id = store.resolve_share_token(token)
    if not analysis_id:
        raise HTTPException(410, "Share link expired or invalid")
    result = store.get(analysis_id)
    if not result:
        raise HTTPException(404, "Analysis not found")
    return result
