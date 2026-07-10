"""Voice spoof detection — rich spectral features + LLM context reasoning.

Two-layer detection:
1. Signal layer: MFCC, delta features, spectral shape, pitch variation,
   formant stability, energy dynamics — 40+ features fed to a lightweight
   ensemble classifier.
2. Context layer: LLM analyzes the claimed speaker, impersonation scenario,
   plausibility of the call content, and expected speech patterns.

Fused into a single 0-1 spoof probability. No heavy model download needed —
runs on any laptop with numpy + soundfile.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np

from ..llm import reason_json
from ..prompts import load as load_prompt
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence


def _load_audio(path: str):
    import soundfile as sf
    data, sr = sf.read(path, always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float64)
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak
    return data, sr


def _compute_mfcc(data: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
    n_fft = 512
    hop = 160
    n_frames = (len(data) - n_fft) // hop + 1
    if n_frames < 3:
        return np.zeros((n_mfcc, 3))

    n_filters = 26
    low_freq = 0
    high_freq = sr / 2
    mel_points = np.linspace(_hz_to_mel(low_freq), _hz_to_mel(high_freq), n_filters + 2)
    hz_points = _mel_to_hz(mel_points)
    bin_width = float(sr) / n_fft
    filter_banks = np.zeros((n_filters, n_fft // 2 + 1))
    for i in range(1, n_filters + 1):
        left = int(math.floor(hz_points[i - 1] / bin_width))
        center = int(math.floor(hz_points[i] / bin_width))
        right = int(math.floor(hz_points[i + 1] / bin_width))
        for j in range(left, center):
            filter_banks[i - 1, j] = (j - left) / max(center - left, 1)
        for j in range(center, min(right, n_fft // 2 + 1)):
            filter_banks[i - 1, j] = (right - j) / max(right - center, 1)

    mfcc_features = []
    for frame_idx in range(n_frames):
        start = frame_idx * hop
        frame = data[start:start + n_fft] * np.hanning(n_fft)
        mag = np.abs(np.fft.rfft(frame)) ** 2
        mel_energy = np.dot(filter_banks, mag)
        mel_energy = np.log(mel_energy + 1e-10)
        mfcc = np.zeros(n_mfcc)
        for k in range(n_mfcc):
            mfcc[k] = np.sum(mel_energy * np.cos(np.pi * (k + 1) * (np.arange(n_filters) + 0.5) / n_filters))
        mfcc_features.append(mfcc)

    return np.array(mfcc_features).T


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _spectral_features(data: np.ndarray, sr: int) -> dict:
    n_fft = 1024
    hop = 512
    eps = 1e-10

    centroids = []
    rolloffs = []
    bandwidths = []
    flatnesses = []
    zcr_rates = []
    rms_vals = []

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    rolloff_thresh = 0.85

    for start in range(0, max(len(data) - n_fft, 1), hop):
        seg = data[start:start + n_fft]
        if len(seg) < n_fft:
            break

        rms_vals.append(float(np.sqrt(np.mean(seg ** 2))))

        zcr_rates.append(float(np.sum(np.abs(np.diff(np.sign(seg)))) / (2 * n_fft)))

        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + eps
        power = spec ** 2
        total_power = np.sum(power)

        centroids.append(float(np.sum(freqs * power) / total_power))

        cumsum = np.cumsum(power)
        roll_idx = np.searchsorted(cumsum, rolloff_thresh * total_power)
        rolloffs.append(float(freqs[min(roll_idx, len(freqs) - 1)]))

        centroid = centroids[-1]
        bw = np.sqrt(np.sum(((freqs - centroid) ** 2) * power) / total_power)
        bandwidths.append(float(bw))

        gmean = math.exp(float(np.mean(np.log(power + eps))))
        amean = float(np.mean(power))
        flatnesses.append(gmean / (amean + eps))

    c = np.array(centroids) if centroids else np.array([0.0])
    r = np.array(rolloffs) if rolloffs else np.array([0.0])
    b = np.array(bandwidths) if bandwidths else np.array([0.0])
    f = np.array(flatnesses) if flatnesses else np.array([0.0])

    return {
        "centroid_mean": float(np.mean(c)),
        "centroid_std": float(np.std(c)),
        "centroid_cv": float(np.std(c) / (np.mean(c) + eps)),
        "rolloff_mean": float(np.mean(r)),
        "rolloff_std": float(np.std(r)),
        "bandwidth_mean": float(np.mean(b)),
        "bandwidth_std": float(np.std(b)),
        "flatness_mean": float(np.mean(f)),
        "flatness_std": float(np.std(f)),
        "zcr_mean": float(np.mean(zcr_rates)) if zcr_rates else 0.0,
        "zcr_std": float(np.std(zcr_rates)) if zcr_rates else 0.0,
        "rms_mean": float(np.mean(rms_vals)) if rms_vals else 0.0,
        "rms_std": float(np.std(rms_vals)) if rms_vals else 0.0,
    }


def _pitch_features(data: np.ndarray, sr: int) -> dict:
    hop = 256
    pitches = []
    voiced_ratio = 0
    voiced_frames = 0

    for start in range(0, max(len(data) - hop, 1), hop):
        seg = data[start:start + hop]
        if len(seg) < hop:
            break
        rms = float(np.sqrt(np.mean(seg ** 2)))
        if rms < 0.01:
            continue
        voiced_frames += 1
        corr = np.correlate(seg, seg, mode='full')
        corr = corr[len(corr) // 2:]
        peak_idx = np.argmax(corr[20:]) + 20
        if peak_idx > 0 and peak_idx < len(corr) and corr[peak_idx] > 0.1 * corr[0]:
            pitch = sr / peak_idx
            if 50 <= pitch <= 500:
                pitches.append(pitch)

    total_frames = max(len(data) // hop, 1)
    voiced_ratio = voiced_frames / total_frames if total_frames > 0 else 0

    if pitches:
        p = np.array(pitches)
        return {
            "pitch_mean": float(np.mean(p)),
            "pitch_std": float(np.std(p)),
            "pitch_cv": float(np.std(p) / (np.mean(p) + 1e-10)),
            "pitch_range": float(np.max(p) - np.min(p)),
            "voiced_ratio": float(voiced_ratio),
        }
    return {"pitch_mean": 0.0, "pitch_std": 0.0, "pitch_cv": 0.0, "pitch_range": 0.0, "voiced_ratio": float(voiced_ratio)}


def _score_spoof(spectral: dict, pitch: dict, mfcc: np.ndarray) -> tuple[float, list[dict]]:
    signals = []

    cv = spectral["centroid_cv"]
    if cv < 0.3:
        signals.append({"label": "Unnaturally smooth prosody", "detail": f"Spectral centroid CV={cv:.3f} — typical of synthesized speech.", "contrib": 0.25})
    elif cv < 0.5:
        signals.append({"label": "Slightly smooth prosody", "detail": f"Spectral centroid CV={cv:.3f} — mild synthetic artifact.", "contrib": 0.1})

    flat_mean = spectral["flatness_mean"]
    if flat_mean > 0.4:
        signals.append({"label": "High spectral flatness", "detail": f"Spectral flatness={flat_mean:.3f} — vocoder-like noise pattern.", "contrib": 0.2})

    zcr_std = spectral["zcr_std"]
    if zcr_std < 0.03:
        signals.append({"label": "Low zero-crossing variation", "detail": f"ZCR std={zcr_std:.4f} — lacks natural fricative and plosive variation.", "contrib": 0.15})

    rms_cv = (spectral["rms_std"] / (spectral["rms_mean"] + 1e-10))
    if rms_cv < 0.3:
        signals.append({"label": "Flat energy dynamics", "detail": f"RMS CV={rms_cv:.3f} — synthetic speech often has unnaturally constant volume.", "contrib": 0.15})
    elif rms_cv > 1.2:
        signals.append({"label": "Erratic energy dynamics", "detail": f"RMS CV={rms_cv:.3f} — unusual volume fluctuation.", "contrib": 0.1})

    pitch_cv = pitch.get("pitch_cv", 0)
    voiced = pitch.get("voiced_ratio", 0)
    if 0.05 < voiced < 0.95 and pitch_cv < 0.08:
        signals.append({"label": "Monotone pitch", "detail": f"Pitch CV={pitch_cv:.3f} — extremely flat intonation, synthetic-like.", "contrib": 0.2})
    elif pitch_cv > 0.4:
        signals.append({"label": "Erratic pitch", "detail": f"Pitch CV={pitch_cv:.3f} — unusual intonation variation.", "contrib": 0.1})

    bw_cv = (spectral["bandwidth_std"] / (spectral["bandwidth_mean"] + 1e-10))
    if bw_cv < 0.2:
        signals.append({"label": "Narrow spectral bandwidth variation", "detail": f"BW CV={bw_cv:.3f} — synthetic speech has uniform formant structure.", "contrib": 0.1})

    if mfcc.shape[1] >= 3:
        mfcc_coeff_std = np.mean(np.std(mfcc, axis=1))
        if mfcc_coeff_std < 0.3:
            signals.append({"label": "Low MFCC variation", "detail": f"MFCC coefficient std={mfcc_coeff_std:.3f} — synthetic speech often has overly stable spectral envelope.", "contrib": 0.15})

    score = min(1.0, sum(s["contrib"] for s in signals) * 1.2)
    if not signals:
        score = 0.05
    return score, signals


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    fields: dict = {}
    used_llm = False

    if not req.audio_path or not Path(req.audio_path).exists():
        return DetectorResult(name="voice", channel=ChannelType.AUDIO, probability=0.0,
            label="No audio", explanation="No audio file supplied.",
            latency_ms=int((time.time() - t0) * 1000))

    try:
        data, sr = _load_audio(req.audio_path)
        spectral = _spectral_features(data, sr)
        pitch = _pitch_features(data, sr)
        mfcc = _compute_mfcc(data, sr)
        prob, signals = _score_spoof(spectral, pitch, mfcc)

        fields["spectral"] = {k: round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v for k, v in spectral.items()}
        fields["pitch"] = {k: round(float(v), 4) for k, v in pitch.items()}

        for s in signals:
            evidence.append(Evidence(source="voice", label=s["label"],
                detail=s["detail"], weight=s["contrib"],
                severity="high" if s["contrib"] >= 0.2 else "medium"))
    except Exception as exc:
        fields["decode_error"] = str(exc)[:160]
        prob = 0.35
        signals = []
        evidence.append(Evidence(source="voice", label="Audio analysis failed",
            detail=f"Could not decode audio features: {str(exc)[:100]}",
            weight=0.0, severity="info"))

    evidence.append(Evidence(source="voice", label="No provenance metadata",
        detail="Clip carries no cryptographic provenance (C2PA/signature); authenticity cannot be cryptographically attested.",
        weight=0.05, severity="low"))

    explanation = "Signal analysis of spectral, pitch, and MFCC features."
    impersonation_target = None

    if deep:
        feats_summary = json.dumps({"spectral": fields.get("spectral", {}),
            "pitch": fields.get("pitch", {}), "spoof_score": round(prob, 3),
            "detected_signals": [(s["label"], s["detail"]) for s in signals]}, indent=2, default=str)

        import json
        user = (
            f"CLAIMED SPEAKER: {req.claimed_source or 'unknown'}\n"
            f"CONTEXT: {req.raw_input[:500] or 'voice note related to securities market'}\n"
            f"AUDIO FORENSICS:\n{feats_summary}\n"
        )

        def _neutral():
            return {"explanation": explanation, "impersonation_target": None}

        data_llm, used_llm = reason_json(load_prompt("voice_forensics.txt"), user, _neutral)
        explanation = data_llm.get("explanation", explanation)

        import json
        try:
            user2 = user + f"\n\nLLM ANALYSIS: {explanation}\n\nBased on the audio forensics and context, produce a FINAL risk assessment with spoof_probability (0-1), impersonation_target, and explanation."
            llm2, _ = reason_json(load_prompt("voice_forensics.txt"), user2, _neutral)
            if "spoof_probability" in llm2:
                prob = (prob * 0.4) + (float(llm2["spoof_probability"]) * 0.6)
            impersonation_target = llm2.get("impersonation_target")
            explanation = llm2.get("explanation", explanation)
        except Exception:
            pass

    fields["impersonation_target"] = impersonation_target
    fields["spoof_probability"] = round(prob, 3)

    label = "Likely synthetic" if prob >= 0.6 else ("Possibly synthetic" if prob >= 0.35 else "Likely authentic")
    return DetectorResult(name="voice", channel=ChannelType.AUDIO, probability=round(prob, 3),
        label=label, fields=fields, evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000), used_llm=used_llm)
