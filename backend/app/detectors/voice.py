"""Synthetic-voice / spoof detector.

MVP uses a signal-feature *proxy* (numpy over the waveform) rather than a heavy
AASIST/wav2vec2 model, so it runs on any laptop with no downloads. The feature
vector and scoring are deliberately isolated in `_score_features` so a real
spoof model can be dropped in behind the same DetectorResult contract.

Signals used (demo-grade, explainable):
  - prosody smoothness  (spectral-centroid variance): TTS/vocoder output is
    often *too* smooth vs. natural speech micro-variation
  - noise floor         : cloned/vocoded audio is frequently unnaturally clean
  - spectral flatness   : vocoder artifacts shift the flatness distribution
  - silence structure   : synthetic clips often lack natural breath/pauses
Provenance (C2PA) is checked as a placeholder — absent for all demo clips.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np

from ..llm import reason_json
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence

_SYS = (
    "You are an audio-forensics analyst for securities-market fraud. Given signal "
    "features of a voice clip and the claimed speaker, write a short risk explanation "
    "and name the likely impersonation target CLASS (e.g. 'regulator official', "
    "'company executive', 'broker support'). Respond ONLY as JSON with keys: "
    "explanation (<=55 words), impersonation_target (string or null)."
)


def _load_audio(path: str):
    import soundfile as sf

    data, sr = sf.read(path, always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)  # mono
    data = data.astype(np.float64)
    if np.max(np.abs(data)) > 0:
        data = data / np.max(np.abs(data))
    return data, sr


def _features(data: np.ndarray, sr: int) -> dict:
    n = len(data)
    duration = n / sr if sr else 0.0
    frame = max(int(0.025 * sr), 256)
    hop = max(int(0.010 * sr), 128)

    rms, centroids, flatness = [], [], []
    eps = 1e-10
    freqs = np.fft.rfftfreq(frame, d=1.0 / sr) if sr else np.array([0.0])
    for start in range(0, max(n - frame, 1), hop):
        seg = data[start : start + frame]
        if len(seg) < frame:
            break
        r = float(np.sqrt(np.mean(seg**2)))
        rms.append(r)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + eps
        power = spec**2
        centroids.append(float(np.sum(freqs * power) / np.sum(power)))
        gmean = math.exp(float(np.mean(np.log(power))))
        amean = float(np.mean(power))
        flatness.append(gmean / (amean + eps))

    rms = np.array(rms) if rms else np.array([0.0])
    centroids = np.array(centroids) if centroids else np.array([0.0])
    flatness = np.array(flatness) if flatness else np.array([0.0])

    peak = float(np.max(rms)) or 1.0
    silence_ratio = float(np.mean(rms < 0.05 * peak))
    voiced = rms[rms >= 0.05 * peak]
    noise_floor = float(np.percentile(rms, 10))
    centroid_cv = float(np.std(centroids) / (np.mean(centroids) + 1e-6))
    rms_cv = float(np.std(voiced) / (np.mean(voiced) + 1e-6)) if len(voiced) else 0.0

    return {
        "duration_s": round(duration, 2),
        "sample_rate": int(sr),
        "silence_ratio": round(silence_ratio, 3),
        "noise_floor": round(noise_floor, 4),
        "spectral_flatness_mean": round(float(np.mean(flatness)), 4),
        "centroid_cv": round(centroid_cv, 3),   # prosody variability
        "rms_cv": round(rms_cv, 3),              # loudness micro-variation
    }


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


_BIAS = -1.3
_WEIGHTS = {
    "smooth_prosody": 2.4,   # centroid variation unusually low
    "clean_noise": 1.7,      # near-zero noise floor
    "flat_dynamics": 1.5,    # little loudness micro-variation
    "few_pauses": 1.1,       # lacks natural breath/pauses
    "high_flatness": 0.9,    # vocoder-like spectral flatness
}
_LABELS = {
    "smooth_prosody": ("Smooth prosody", "spectral-centroid variation {v} (low = TTS/vocoded-like)"),
    "clean_noise": ("Low noise floor", "noise floor {v} (very clean recording)"),
    "flat_dynamics": ("Flat loudness dynamics", "loudness micro-variation {v} (low = synthesized-like)"),
    "few_pauses": ("Few natural pauses", "silence ratio {v} (lacks natural breath/pauses)"),
    "high_flatness": ("High spectral flatness", "flatness {v} (vocoder-artifact range)"),
}


def _signals(f: dict) -> dict[str, tuple[float, float]]:
    """Return {name: (signal_0..1, raw_feature_value)}."""
    dur = f.get("duration_s", 0)
    return {
        "smooth_prosody": (_clamp01((0.6 - f["centroid_cv"]) / 0.6), f["centroid_cv"]),
        "clean_noise": (_clamp01((0.015 - f["noise_floor"]) / 0.015), f["noise_floor"]),
        "flat_dynamics": (_clamp01((0.5 - f["rms_cv"]) / 0.5), f["rms_cv"]),
        "few_pauses": (_clamp01((0.1 - f["silence_ratio"]) / 0.1) if dur > 2.5 else 0.0, f["silence_ratio"]),
        "high_flatness": (_clamp01((f["spectral_flatness_mean"] - 0.2) / 0.4), f["spectral_flatness_mean"]),
    }


def _score_features(f: dict) -> tuple[float, list[tuple[str, str, float]]]:
    """Return (spoof_probability, [(label, detail, contribution)]) — continuous."""
    sig = _signals(f)
    z = _BIAS + sum(_WEIGHTS[k] * s for k, (s, _) in sig.items())
    prob = _sigmoid(z)

    reasons: list[tuple[str, str, float]] = []
    for k, (s, raw) in sorted(sig.items(), key=lambda kv: -_WEIGHTS[kv[0]] * kv[1][0]):
        if s <= 0.12:
            continue
        contrib = _WEIGHTS[k] * s
        label, tmpl = _LABELS[k]
        reasons.append((label, tmpl.format(v=raw) + f" · contribution {contrib:+.2f}", round(contrib / 8.0, 3)))
    return prob, reasons


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    fields: dict = {"provenance_available": False}
    used_llm = False

    if not req.audio_path or not Path(req.audio_path).exists():
        return DetectorResult(
            name="voice", channel=ChannelType.AUDIO, probability=0.0,
            label="No audio", explanation="No audio file supplied.",
            latency_ms=int((time.time() - t0) * 1000),
        )

    try:
        data, sr = _load_audio(req.audio_path)
        feats = _features(data, sr)
        prob, reasons = _score_features(feats)
        fields["features"] = feats
        for label, detail, w in reasons:
            evidence.append(Evidence(source="voice", label=label, detail=detail,
                                     weight=abs(w), severity="medium" if w > 0 else "info"))
    except Exception as exc:
        fields["decode_error"] = str(exc)[:160]
        prob = 0.4
        evidence.append(Evidence(source="voice", label="Could not decode audio features",
                                 detail="Falling back to provenance-only assessment.", weight=0.0, severity="info"))
        feats = {}

    evidence.append(Evidence(
        source="voice", label="No provenance metadata (C2PA)",
        detail="Clip carries no cryptographic provenance; authenticity cannot be attested.",
        weight=0.08, severity="low"))

    impersonation_target = None
    explanation = "Signal-feature proxy assessment of synthetic-speech likelihood."
    if deep:
        user = (
            f"CLAIMED SPEAKER/SOURCE: {req.claimed_source or 'unknown'}\n"
            f"CONTEXT: {req.raw_input[:400] or 'voice note related to securities market'}\n"
            f"SIGNAL FEATURES: {feats}\n"
            f"HEURISTIC SPOOF PROBABILITY: {round(prob,3)}\n"
        )

        def _fallback():
            tgt = None
            src = (req.claimed_source or "").lower()
            if any(k in src for k in ["sebi", "rbi", "regulator"]):
                tgt = "regulator official"
            elif any(k in src for k in ["ceo", "cfo", "executive", "director", "md"]):
                tgt = "company executive"
            elif any(k in src for k in ["broker", "support", "relationship"]):
                tgt = "broker support"
            return {
                "explanation": "Rule-based: spoof likelihood driven by prosody smoothness / clean noise floor; "
                "clip lacks provenance metadata.",
                "impersonation_target": tgt,
            }

        data_llm, used_llm = reason_json(_SYS, user, _fallback)
        explanation = data_llm.get("explanation", explanation)
        impersonation_target = data_llm.get("impersonation_target")

    fields["impersonation_target"] = impersonation_target
    fields["spoof_probability"] = round(prob, 3)

    label = "Likely synthetic voice" if prob >= 0.6 else ("Possibly synthetic" if prob >= 0.4 else "Likely authentic voice")
    return DetectorResult(
        name="voice", channel=ChannelType.AUDIO, probability=round(prob, 3),
        label=label, fields=fields, evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000), used_llm=used_llm,
    )
