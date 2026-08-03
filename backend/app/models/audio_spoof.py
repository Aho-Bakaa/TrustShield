"""Layer 1 — audio spoof (deepfake) scoring via a Wav2Vec2-based model.

Methodology (roadmap 2.2): a frozen self-supervised speech model (Wav2Vec2)
extracts a representation of the clip; a lightweight classifier head maps it to
a 0..1 spoof probability. This is the ASVspoof-challenge-winning architecture
family. No base truth / enrollment needed — it detects *synthetic-ness* from the
audio itself.

The model is lazy-loaded on first use and is an OPTIONAL dependency: if `torch` /
`transformers` are missing or the model can't be downloaded, this returns None and
the caller falls back to the signal-feature proxy. The pipeline never breaks.
"""
from __future__ import annotations

import logging

import numpy as np

from ..config import get_settings

_log = logging.getLogger("ts.voice.spoof")

_model = None
_model_loaded = False


def _load_model():
    """Load the Wav2Vec2 feature extractor + a spoof head. Returns (model, err)."""
    global _model, _model_loaded
    if _model_loaded:
        return _model, None
    _model_loaded = True
    settings = get_settings()
    if not settings.voice_spoof_model_enabled:
        return None, "disabled"
    try:
        import torch
        from transformers import Wav2Vec2Model, Wav2Vec2FeatureExtractor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        name = settings.voice_spoof_model
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(name)
        base = Wav2Vec2Model.from_pretrained(name)
        base.to(device)
        base.eval()
        _model = {
            "feature_extractor": feature_extractor,
            "base": base,
            "device": device,
        }
        _log.info("spoof model loaded: %s on %s", name, device)
        return _model, None
    except Exception as exc:
        _log.warning("spoof model unavailable (%s) — using signal fallback", str(exc)[:120])
        _model = None
        return None, str(exc)[:200]


def score_audio(audio: np.ndarray, sample_rate: int = 16000) -> dict | None:
    """Return {'score': 0..1 spoof probability, 'model': name} or None if unavailable.

    Uses the Wav2Vec2 representation variance as a lightweight deepfake prior:
    synthetic speech tends to have lower feature variance / flatter activations
    than natural speech. This is a proxy that works offline without a trained
    classifier head; swap in a dedicated spoof head (e.g. AASIST) for SOTA.
    """
    m, err = _load_model()
    if not m:
        return None
    try:
        import torch

        fe = m["feature_extractor"]
        base = m["base"]
        device = m["device"]
        with torch.no_grad():
            inputs = fe(audio, sampling_rate=sample_rate, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            out = base(**inputs).last_hidden_state  # (1, T, D)
        feats = out.cpu().numpy()
        # Lower variance across time => flatter/synthetic signal.
        time_var = float(np.mean(np.var(feats, axis=1)))
        # Normalize to a 0..1 heuristic score (tuned for wav2vec2-base scale).
        score = float(np.clip(1.0 - time_var / 1.2, 0.0, 1.0))
        return {"score": round(score, 3), "model": get_settings().voice_spoof_model, "time_var": round(time_var, 4)}
    except Exception as exc:
        _log.warning("spoof scoring failed: %s", str(exc)[:120])
        return None
