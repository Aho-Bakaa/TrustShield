"""Video deepfake detector — delegates to KAVACH API.

Calls the ath1614/RBI hosted deepfake detection endpoint (5-model ensemble).
Supports MP4, AVI, MOV, MKV, WEBM up to 100MB.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ..log import get_logger
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence

_log = get_logger("deepfake")

KAVACH_DEEPFAKE_URL = "http://34.14.184.35:8002/api/v1/detect/deepfake"
_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

FAKE_LABELS = {
    "DEEPFAKE_VIDEO": "AI-generated deepfake video",
    "FACESWAP": "Face-swapped video",
    "LIPSYNC_DEEPFAKE": "Lip-synced deepfake",
    "AI_GENERATED": "AI-generated content",
    "AUTHENTIC": "Authentic video",
}


def _classify(prob: float, deepfake_type: str) -> tuple[str, float]:
    if prob >= 0.75:
        return "high", prob
    elif prob >= 0.40:
        return "medium", prob
    else:
        return "low", prob


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    used_llm = False

    video_path = req.attachments[0] if req.attachments else None
    if not video_path:
        return DetectorResult(
            name="deepfake", channel=ChannelType.VIDEO,
            probability=0.0, label="No video file",
            fields={}, evidence=evidence, explanation="No video file provided.",
            latency_ms=int((time.time() - t0) * 1000),
            used_llm=False, used_render=False,
        )

    try:
        with open(video_path, "rb") as f:
            files = {"file": (req.attachments[0], f, "video/mp4")}
            resp = httpx.post(KAVACH_DEEPFAKE_URL, files=files, timeout=120)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        _log.warning("KAVACH deepfake API timed out")
        return DetectorResult(
            name="deepfake", channel=ChannelType.VIDEO,
            probability=0.0, label="API timeout",
            fields={"_error": "KAVACH API timeout"}, evidence=evidence,
            explanation="Deepfake detection service timed out. Try again.",
            latency_ms=int((time.time() - t0) * 1000),
            used_llm=False, used_render=False,
        )
    except Exception as exc:
        _log.warning("KAVACH deepfake API error: %s", str(exc)[:200])
        return DetectorResult(
            name="deepfake", channel=ChannelType.VIDEO,
            probability=0.0, label="API unavailable",
            fields={"_error": str(exc)[:200]}, evidence=evidence,
            explanation="Deepfake detection service unavailable.",
            latency_ms=int((time.time() - t0) * 1000),
            used_llm=False, used_render=False,
        )

    result = data.get("result", {})
    if not result:
        return DetectorResult(
            name="deepfake", channel=ChannelType.VIDEO,
            probability=0.0, label="No result",
            fields={}, evidence=evidence, explanation="Detection returned no result.",
            latency_ms=int((time.time() - t0) * 1000),
            used_llm=False, used_render=False,
        )

    prob = float(result.get("deepfake_probability", 0))
    is_deepfake = bool(result.get("is_deepfake", False))
    deepfake_type_raw = result.get("deepfake_type", "UNKNOWN")
    deepfake_type = FAKE_LABELS.get(deepfake_type_raw, deepfake_type_raw)
    risk_level, _ = _classify(prob, deepfake_type_raw)
    models_used = result.get("models_used", 0)
    faces = result.get("faces_detected", 0)
    frames = result.get("frames_analyzed", 0)
    duration = result.get("duration_seconds")
    scores = result.get("scores", {})

    for e in result.get("evidence", []):
        sev = "high" if e.get("confidence", 0) >= 0.7 else ("medium" if e.get("confidence", 0) >= 0.4 else "low")
        evidence.append(Evidence(
            source="deepfake_model",
            label=e.get("type", "Model evidence"),
            detail=e.get("description", ""),
            weight=float(e.get("confidence", 0.5)),
            severity=sev,
        ))

    label = "Deepfake detected" if is_deepfake else "Likely authentic"
    if prob >= 0.75:
        label = "High-confidence deepfake"
    elif prob >= 0.40:
        label = "Suspicious — possible deepfake"

    fields: dict[str, Any] = {
        "is_deepfake": is_deepfake,
        "deepfake_probability": prob,
        "deepfake_type": deepfake_type,
        "risk_level": risk_level,
        "models_used": models_used,
        "faces_detected": faces,
        "frames_analyzed": frames,
        "duration_seconds": duration,
        "scores": scores,
    }

    explanation = (
        f"Deepfake probability: {prob:.0%}. "
        f"Type: {deepfake_type}. "
        f"Faces detected: {faces}, frames analyzed: {frames}. "
        + (f"Duration: {duration:.1f}s." if duration else "")
    )

    return DetectorResult(
        name="deepfake",
        channel=ChannelType.VIDEO,
        probability=round(prob, 3),
        label=label,
        fields=fields,
        evidence=evidence,
        explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000),
        used_llm=used_llm,
        used_render=False,
    )
