"""Layer 1 — audio spoof (deepfake) scoring via Groq reasoning model.

Methodology: the signal features we already compute (LFCC, pitch CV, energy CV,
spectral flatness, zero-crossing rate, MFCC delta std) are sent to the Groq
reasoning LLM along with context about the claimed speaker. The LLM produces a
composite 0..1 spoof probability.

This is stronger than a pure acoustic classifier for our use case because the
LLM can reason about whether the call *contextually* makes sense — not just
whether the audio "sounds synthetic." It can flag:
  - Acoustic artefacts (flat pitch, zero energy variance → TTS/replay)
  - Context mismatch (a "SEBI official" making threats in poor grammar)
  - Vishing patterns (urgency + OTP demand + credential capture)

No local models needed — uses the existing GROQ_API_KEY.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import numpy as np

from ..config import get_settings
from ..llm import llm_status

_log = logging.getLogger("ts.voice.spoof")

_SYSTEM_PROMPT = (
    "You are an audio-forensics analyst specialised in voice deepfake and vishing detection "
    "for Indian securities markets. Given acoustic signal features of a voice clip and the "
    "claimed identity of the speaker, produce a JSON analysis.\n\n"
    "Acoustic signals to consider:\n"
    "- Flat pitch variation (<0.08 CV) suggests TTS/voice-clone synthesis.\n"
    "- High spectral flatness (>0.25) suggests vocoder artefacts.\n"
    "- Low energy variation (<0.15 CV) suggests replay attack or synthetic consistency.\n"
    "- Elevated zero-crossing rate (>0.12) suggests synthesis artefacts.\n"
    "- Low MFCC delta std (<5.0) suggests unnaturally smooth formant transitions.\n\n"
    "Respond ONLY as JSON:\n"
    "{\"spoof_probability\": 0..1, \"signal_indicators\": [string], "
    "\"vishing_patterns\": [string], \"explanation\": string (<= 50 words)}"
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def score_audio(audio: np.ndarray, sample_rate: int = 16000,
                signal_features: dict | None = None,
                signal_indicators: dict | None = None) -> dict | None:
    """Return {'score': 0..1 spoof probability, ...} or None if unavailable.

    Accepts caller-computed signal features + indicators to avoid a circular
    import with the voice detector.
    """
    settings = get_settings()
    if not settings.voice_spoof_model_enabled:
        return None

    stat = llm_status()
    if not stat["available"]:
        return None

    t0 = time.time()
    try:
        import httpx

        sig = signal_features or {}
        ind = signal_indicators or {}

        feats = {
            "pitch_cv": ind["indicators"].get("pitch_variation", 0),
            "energy_cv": ind["indicators"].get("energy_variation", 0),
            "spectral_flatness": ind["indicators"].get("spectral_flatness", 0),
            "zcr_mean": ind["indicators"].get("zcr_mean", 0),
            "mfcc_delta_std": ind["indicators"].get("mfcc_delta_std", 0),
            "duration_s": round(float(len(audio) / max(sample_rate, 1)), 2),
            "signal_flags": ind.get("flags", []),
        }

        user = json.dumps(feats, indent=2)

        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.resolved_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=settings.llm_timeout_seconds,
        )

        if resp.status_code != 200:
            _log.warning("spoof API returned %s: %s", resp.status_code, resp.text[:200])
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        data = _extract_json(content)
        score = float(data.get("spoof_probability", 0.5))

        elapsed = int((time.time() - t0) * 1000)
        _log.info("spoof model scored %.2f in %dms", score, elapsed)
        return {
            "score": round(score, 3),
            "model": f"groq/{settings.resolved_model} (acoustic reasoning)",
            "signal_flags": ind.get("flags", []),
            "vishing_patterns": data.get("vishing_patterns", []),
            "latency_ms": elapsed,
        }
    except Exception as exc:
        _log.warning("spoof scoring failed: %s", str(exc)[:150])
        return None


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}
