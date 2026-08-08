"""Local IndicWav2Vec2-Hindi voice spoof detector.

Loads from local model directory (app/data/models/voice).
Falls back to Groq LLM acoustic reasoning if model not found.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

_log = logging.getLogger("ts.voice.kavach")

MODEL_DIR = "app/data/models/voice"
SAMPLE_RATE = 16000
MAX_DURATION_S = 10.0

_pipeline = None


def _ensure_model():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline
        import torch

        device = 0 if torch.cuda.is_available() else -1
        _log.info("loading indicwav2vec from %s on %s", MODEL_DIR, "cuda" if device >= 0 else "cpu")
        _pipeline = pipeline("audio-classification", model=MODEL_DIR, device=device)
        _log.info("indicwav2vec loaded")
        return _pipeline
    except ImportError:
        _log.warning("transformers/torch not installed")
        return None
    except Exception as exc:
        _log.warning("indicwav2vec load failed: %s", str(exc)[:200])
        return None


def score(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> dict | None:
    model = _ensure_model()
    if model is None:
        return None

    t0 = time.time()
    try:
        if sample_rate != SAMPLE_RATE:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=SAMPLE_RATE)

        max_samples = int(SAMPLE_RATE * MAX_DURATION_S)
        if len(audio) > max_samples:
            audio = audio[:max_samples]

        result = model({"array": audio, "sampling_rate": SAMPLE_RATE}, top_k=1)
        label = result[0]["label"] if result else "unknown"
        conf = float(result[0]["score"]) if result else 0.5
        is_spoof = "spoof" in label.lower()
        spoof_prob = conf if is_spoof else 1.0 - conf

        elapsed = int((time.time() - t0) * 1000)
        _log.info("indicwav2vec scored %.3f (%s) in %dms", spoof_prob, label, elapsed)
        return {"score": round(spoof_prob, 3), "model": "indicwav2vec-hindi (local)", "label": label, "latency_ms": elapsed}
    except Exception as exc:
        _log.warning("indicwav2vec scoring failed: %s", str(exc)[:200])
        return None
