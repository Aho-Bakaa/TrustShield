"""Layer 3 — ASR transcription for voice content analysis.

Transcribes an audio clip using the Groq Whisper API so the content can feed
the same claims / web-search / verdict pipeline used for emails.

No local models required — uses the existing GROQ_API_KEY. Fast (~1-3s per
30s clip), ~$0.04/hr of audio. Degrades gracefully when the Groq key is absent
(via the `llm_available` check).
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

import numpy as np
import soundfile as sf

from .config import get_settings
from .llm import llm_status

_log = logging.getLogger("ts.voice.asr")


def transcribe(audio: np.ndarray, sample_rate: int = 16000) -> dict[str, Any] | None:
    """Transcribe audio via Groq Whisper API.

    Returns {'text': str, 'language': str} or None if unavailable/broken.
    """
    settings = get_settings()
    if not settings.voice_asr_enabled:
        return None

    stat = llm_status()
    if not stat["available"]:
        _log.info("ASR skipped: LLM key not configured")
        return None

    try:
        import httpx

        # Convert numpy → WAV bytes (Groq accepts multipart audio file uploads).
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        buf.seek(0)

        files = {"file": ("audio.wav", buf, "audio/wav")}
        data = {"model": "whisper-large-v3-turbo", "response_format": "json"}

        resp = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            files=files,
            data=data,
            timeout=45,
        )

        if resp.status_code != 200:
            _log.warning("Groq ASR returned %s: %s", resp.status_code, resp.text[:200])
            return None

        result = resp.json()
        text = (result.get("text") or "").strip()
        lang = result.get("language", "")
        _log.info("ASR transcribed %d chars (lang=%s)", len(text), lang)
        return {"text": text, "language": lang}
    except Exception as exc:
        _log.warning("ASR failed: %s", str(exc)[:150])
        return None
