"""Layer 3 — ASR transcription for voice content analysis.

Transcribes an audio clip to text so the SAME phishing/claims pipeline used for
emails can verify the *content* of a call (false claims, urgency, credential
demands) regardless of whether the voice is synthetic.

Uses faster-whisper (a CTranslate2-accelerated Whisper) if available, else the
`openai-whisper` package. Lazy-loaded, optional dependency — if neither is
installed, returns None and the caller skips content analysis.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .config import get_settings

_log = logging.getLogger("ts.voice.asr")

_model = None
_model_loaded = False


def _load_model():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True
    settings = get_settings()
    if not settings.voice_asr_enabled:
        return None
    try:
        from faster_whisper import WhisperModel  # type: ignore

        _model = {"kind": "faster_whisper", "model": WhisperModel(settings.voice_asr_model, device="cpu", compute_type="int8")}
        _log.info("ASR model loaded: faster-whisper %s", settings.voice_asr_model)
        return _model
    except Exception as exc:
        _log.info("faster-whisper unavailable (%s) — trying openai-whisper", str(exc)[:100])
    try:
        import whisper  # type: ignore

        _model = {"kind": "openai_whisper", "model": whisper.load_model(settings.voice_asr_model)}
        _log.info("ASR model loaded: openai-whisper %s", settings.voice_asr_model)
        return _model
    except Exception as exc:
        _log.warning("no ASR model available (%s) — content analysis skipped", str(exc)[:100])
        _model = None
        return None


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> dict[str, Any] | None:
    """Transcribe audio to text. Returns {'text': str, 'language': str} or None."""
    m = _load_model()
    if not m:
        return None
    try:
        if m["kind"] == "faster_whisper":
            segments, info = m["model"].transcribe(audio, sampling_rate=sample_rate)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return {"text": text, "language": info.language}
        # openai-whisper
        import numpy as _np

        audio_fp32 = audio.astype(_np.float32)
        result = m["model"].transcribe(audio_fp32)
        return {"text": (result.get("text") or "").strip(), "language": result.get("language", "")}
    except Exception as exc:
        _log.warning("ASR failed: %s", str(exc)[:150])
        return None
