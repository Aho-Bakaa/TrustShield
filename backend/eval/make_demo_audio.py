"""Generate demo audio clips with distinct signal profiles.

These are SYNTHETIC PLACEHOLDERS so the voice pipeline runs end-to-end on any
machine with no recordings. Replace the files in data/demo_dataset/audio with
real authentic/cloned clips for a stronger demo — the detector and labels below
work the same way.

  - "synthetic-like": very clean, constant amplitude, smooth/steady spectrum
    (mimics TTS/vocoder output) -> high spoof score.
  - "natural-like": added noise floor, amplitude tremolo, varying pitch, and
    natural pauses -> low spoof score.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 16000
DUR = 5.0
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "demo_dataset" / "audio"
OUT.mkdir(parents=True, exist_ok=True)


def _synthetic(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    base = 140 + seed * 15  # steady fundamental
    sig = 0.6 * np.sin(2 * np.pi * base * t)
    sig += 0.2 * np.sin(2 * np.pi * base * 2 * t)  # steady harmonic
    # almost no amplitude variation, negligible noise, no pauses
    sig += rng.normal(0, 0.0008, len(t))
    return sig / (np.max(np.abs(sig)) + 1e-9) * 0.9


def _natural(seed: int) -> np.ndarray:
    rng = np.random.default_rng(1000 + seed)
    n = int(SR * DUR)
    t = np.linspace(0, DUR, n, endpoint=False)
    sig = np.zeros(n)
    # segments with different pitch (prosody variation) + pauses
    pos = 0
    while pos < n:
        seg_len = int(SR * rng.uniform(0.25, 0.6))
        f = rng.uniform(110, 260)
        end = min(pos + seg_len, n)
        tt = t[pos:end]
        env = rng.uniform(0.3, 1.0) * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(3, 7) * tt))
        sig[pos:end] += env * np.sin(2 * np.pi * f * tt)
        pos = end
        # insert a short pause
        gap = int(SR * rng.uniform(0.05, 0.18))
        pos += gap
    sig += rng.normal(0, 0.03, n)  # realistic noise floor
    return sig / (np.max(np.abs(sig)) + 1e-9) * 0.9


def main() -> None:
    labels = []
    for i in range(1, 4):
        p = OUT / f"voice_synth_{i:02d}.wav"
        sf.write(p, _synthetic(i).astype(np.float32), SR)
        labels.append({"id": p.stem, "file": str(p), "label": "malicious", "note": "synthetic-like profile"})
    for i in range(1, 4):
        p = OUT / f"voice_real_{i:02d}.wav"
        sf.write(p, _natural(i).astype(np.float32), SR)
        labels.append({"id": p.stem, "file": str(p), "label": "legit", "note": "natural-like profile"})

    (OUT / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"Wrote {len(labels)} clips to {OUT}")


if __name__ == "__main__":
    main()
