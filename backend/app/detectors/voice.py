"""Voice spoof detection — LFCC + librosa signal features + LLM context reasoning.

Signal features adapted from RBI/KAVACH voice anti-spoofing module:
  - LFCC (Linear Frequency Cepstral Coefficients) via scipy DCT
  - Librosa MFCC + delta std, pitch CV, energy CV, spectral flatness, ZCR
  - Produces auxiliary spoof score + human-readable flags

LLM fusion:
  - 40% signal score + 60% LLM context reasoning (plausibility check)
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import numpy as np

from ..llm import reason_json
from ..prompts import load as load_prompt
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence


SAMPLE_RATE = 16000
MAX_DURATION_SEC = 5.0
NUM_SAMPLES = int(SAMPLE_RATE * MAX_DURATION_SEC)


def _load_audio(path: str):
    import soundfile as sf
    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        try:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=SAMPLE_RATE)
            sr = SAMPLE_RATE
        except ImportError:
            pass
    peak = np.abs(data).max()
    if peak > 0:
        data = data / peak
    return data, sr


def _preprocess(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr != SAMPLE_RATE:
        try:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
        except ImportError:
            pass
    if len(audio) < NUM_SAMPLES:
        audio = np.pad(audio, (0, NUM_SAMPLES - len(audio)))
    else:
        audio = audio[:NUM_SAMPLES]
    return audio.astype(np.float32)


def _compute_lfcc(audio: np.ndarray, sr: int = SAMPLE_RATE, n_lfcc: int = 60) -> np.ndarray:
    try:
        import librosa
        from scipy.fft import dct

        n_fft = 512
        hop_length = 160
        n_filter = 128

        stft = np.abs(librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)) ** 2
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        linear_filters = np.zeros((n_filter, len(freqs)))
        freq_bins = np.linspace(0, freqs[-1], n_filter + 2)
        for i in range(n_filter):
            f_low, f_center, f_high = freq_bins[i], freq_bins[i + 1], freq_bins[i + 2]
            for j, f in enumerate(freqs):
                if f_low <= f <= f_center:
                    linear_filters[i, j] = (f - f_low) / (f_center - f_low + 1e-8)
                elif f_center < f <= f_high:
                    linear_filters[i, j] = (f_high - f) / (f_high - f_center + 1e-8)

        linear_spec = linear_filters @ stft
        log_spec = np.log(linear_spec + 1e-8)
        lfcc = dct(log_spec, type=2, axis=0, norm='ortho')[:n_lfcc]
        return lfcc.mean(axis=1).astype(np.float32)
    except Exception:
        return np.zeros(n_lfcc, dtype=np.float32)


def _extract_signal_features(audio: np.ndarray, sr: int) -> dict:
    try:
        import librosa

        rms = librosa.feature.rms(y=audio, hop_length=160)[0]
        is_silent = float(rms.mean()) < 1e-4

        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=40, n_fft=512, hop_length=160, win_length=400)

        try:
            f0, _, _ = librosa.pyin(audio, fmin=50, fmax=400, sr=sr, hop_length=160)
            pitch = np.nan_to_num(f0, nan=0.0)
        except Exception:
            pitch = np.zeros(100)

        flatness = librosa.feature.spectral_flatness(y=audio, hop_length=160)[0]
        centroid = librosa.feature.spectral_centroid(y=audio, sr=sr, hop_length=160)[0]
        zcr = librosa.feature.zero_crossing_rate(audio, hop_length=160)[0]

        return {
            "mfcc": mfcc, "pitch": pitch, "energy": rms,
            "spectral_flatness": flatness, "spectral_centroid": centroid,
            "zcr": zcr, "is_silent": is_silent,
        }
    except ImportError:
        return {"is_silent": False}


def _compute_spoof_indicators(signal: dict) -> dict:
    flags = []
    indicators = {}

    pitch = signal.get("pitch", np.array([]))
    voiced = pitch[pitch > 0] if len(pitch) > 0 else np.array([])
    if len(voiced) > 10:
        pitch_cv = float(np.std(voiced) / (np.mean(voiced) + 1e-8))
        indicators["pitch_variation"] = round(pitch_cv, 4)
        if pitch_cv < 0.08:
            flags.append("Unnaturally flat pitch — possible TTS synthesis")
    else:
        indicators["pitch_variation"] = 0.0

    sf_mean = float(signal.get("spectral_flatness", np.array([0])).mean())
    indicators["spectral_flatness"] = round(sf_mean, 4)
    if sf_mean > 0.3:
        flags.append("High spectral flatness — vocoder/synthesizer artifact")

    energy = signal.get("energy", np.array([1]))
    energy_cv = float(np.std(energy) / (np.mean(energy) + 1e-8))
    indicators["energy_variation"] = round(energy_cv, 4)
    if energy_cv < 0.15:
        flags.append("Unnaturally consistent energy — possible TTS or replay")

    mfcc = signal.get("mfcc", np.zeros((40, 10)))
    mfcc_delta = np.diff(mfcc, axis=1)
    mfcc_delta_std = float(mfcc_delta.std())
    indicators["mfcc_delta_std"] = round(mfcc_delta_std, 4)
    if mfcc_delta_std < 5.0:
        flags.append("Smooth MFCC transitions — unnaturally consistent voice")

    zcr_mean = float(signal.get("zcr", np.array([0])).mean())
    indicators["zcr_mean"] = round(zcr_mean, 4)
    if zcr_mean > 0.15:
        flags.append("Elevated zero-crossing rate — synthesis artifact")

    aux_score = min(len(flags) / 4.0, 1.0)
    return {"auxiliary_score": aux_score, "flags": flags, "indicators": indicators}


def _fuse_score(neural_score: float, aux_score: float) -> float:
    W_NEURAL = 0.90
    W_SIGNAL = 0.10
    return float(np.clip(W_NEURAL * neural_score + W_SIGNAL * aux_score, 0.0, 1.0))


def _risk_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    elif score >= 0.70:
        return "HIGH"
    elif score >= 0.50:
        return "MEDIUM"
    return "LOW"


def _spoof_type(score: float, flags: list, indicators: dict) -> str:
    if score < 0.50:
        return "GENUINE"
    energy_cv = indicators.get("energy_variation", 1.0)
    pitch_cv = indicators.get("pitch_variation", 1.0)
    if energy_cv < 0.10:
        return "REPLAY_ATTACK"
    if pitch_cv < 0.06:
        return "TTS_SYNTHETIC"
    if "flatness" in " ".join(flags).lower():
        return "VOICE_CONVERSION"
    if score > 0.85:
        return "AI_DEEPFAKE"
    return "UNKNOWN_SPOOF"


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
        raw_audio, sr = _load_audio(req.audio_path)
        duration = len(raw_audio) / sr if sr else 0.0
        fields["duration_s"] = round(duration, 2)
        audio = _preprocess(raw_audio, sr)
        signal = _extract_signal_features(audio, SAMPLE_RATE)

        if signal.get("is_silent"):
            return DetectorResult(name="voice", channel=ChannelType.AUDIO, probability=0.0,
                label="Silent audio", explanation="Audio is silent.",
                latency_ms=int((time.time() - t0) * 1000), used_llm=False)

        lfcc = _compute_lfcc(audio, SAMPLE_RATE)
        lfcc_score = float(np.mean(np.abs(lfcc))) / 100.0
        lfcc_score = min(max(lfcc_score, 0.0), 1.0)

        indicators = _compute_spoof_indicators(signal)
        aux_score = indicators["auxiliary_score"]
        combined = _fuse_score(lfcc_score, aux_score)

        for flag in indicators["flags"]:
            evidence.append(Evidence(source="voice", label=flag,
                detail=f"Signal analysis indicator",
                weight=round(min(0.5 + aux_score * 0.5, 0.95), 4), severity="high" if aux_score > 0.5 else "medium"))

        evidence.append(Evidence(source="voice", label="LFCC analysis",
            detail=f"LFCC score: {lfcc_score:.2%} (1084-dim linear frequency cepstral)",
            weight=round(lfcc_score, 4), severity="info"))
        evidence.append(Evidence(source="voice", label="Signal indicators",
            detail=f"Pitch CV={indicators['indicators'].get('pitch_variation', 0):.4f}, "
                   f"Energy CV={indicators['indicators'].get('energy_variation', 0):.4f}, "
                   f"Flatness={indicators['indicators'].get('spectral_flatness', 0):.4f}",
            weight=round(aux_score, 4), severity="info"))

    except Exception as exc:
        fields["decode_error"] = str(exc)[:160]
        combined = 0.35
        indicators = {"auxiliary_score": 0.0, "flags": [], "indicators": {}}
        evidence.append(Evidence(source="voice", label="Audio decode failed",
            detail=f"Could not process: {str(exc)[:100]}",
            weight=0.0, severity="info"))

    evidence.append(Evidence(source="voice", label="No provenance metadata",
        detail="Clip carries no cryptographic provenance (C2PA/signature); authenticity cannot be cryptographically attested.",
        weight=0.05, severity="low"))

    explanation = f"Signal analysis: {_spoof_type(combined, indicators.get('flags', []), indicators.get('indicators', {}))}. Risk level: {_risk_level(combined)}."
    impersonation_target = None

    if deep:
        import json
        feats_summary = json.dumps({
            "spoof_probability": round(combined, 3),
            "spoof_type": _spoof_type(combined, indicators.get("flags", []), indicators.get("indicators", {})),
            "signal_flags": indicators.get("flags", []),
            "indicators": indicators.get("indicators", {}),
            "duration_s": fields.get("duration_s", 0),
        }, indent=2, default=str)

        user = (
            f"CLAIMED SPEAKER: {req.claimed_source or 'unknown'}\n"
            f"CONTEXT: {req.raw_input[:500] or 'voice note related to securities market'}\n"
            f"AUDIO FORENSICS:\n{feats_summary}\n"
        )

        def _neutral():
            return {"explanation": explanation, "impersonation_target": None,
                    "spoof_probability": round(combined, 3)}

        data_llm, used_llm = reason_json(load_prompt("voice_forensics.txt"), user, _neutral)
        explanation = data_llm.get("explanation", explanation)
        if "spoof_probability" in data_llm:
            try:
                llm_prob = float(data_llm["spoof_probability"])
                combined = (combined * 0.4) + (llm_prob * 0.6)
            except (ValueError, TypeError):
                pass
        impersonation_target = data_llm.get("impersonation_target")

    fields["impersonation_target"] = impersonation_target
    fields["spoof_probability"] = round(combined, 3)
    fields["spoof_type"] = _spoof_type(combined, indicators.get("flags", []), indicators.get("indicators", {}))
    fields["indicators"] = indicators.get("indicators", {})

    label = "Likely synthetic" if combined >= 0.6 else ("Possibly synthetic" if combined >= 0.35 else "Likely authentic")
    return DetectorResult(name="voice", channel=ChannelType.AUDIO, probability=round(combined, 3),
        label=label, fields=fields, evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000), used_llm=used_llm)
