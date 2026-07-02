"""Voice detector tests — continuous, feature-driven, no filename cheat.

Reuses the same generators as the demo-audio maker so the test signals have
realistic prosody variation (a natural clip must vary *frequency*, not just
amplitude — a single-tone sine is legitimately synthetic-looking).
"""
import numpy as np

from app.detectors.voice import _features, _score_features
from eval.make_demo_audio import SR, _natural, _synthetic


def _prob(sig):
    return _score_features(_features(sig, SR))[0]


def test_clean_steady_synthetic_scores_high():
    assert _prob(_synthetic(1)) > 0.6


def test_natural_varied_scores_lower():
    assert _prob(_natural(1)) < 0.55


def test_synthetic_scores_above_natural():
    assert _prob(_synthetic(2)) > _prob(_natural(2))


def test_score_is_continuous_not_bucketed():
    # Blend synthetic <-> natural; scores should vary continuously, not snap to buckets.
    syn, nat = _synthetic(1), _natural(1)
    n = min(len(syn), len(nat))
    probs = []
    for a in (0.0, 0.35, 0.7, 1.0):
        mix = (1 - a) * syn[:n] + a * nat[:n]
        probs.append(round(_prob(mix), 3))
    assert len(set(probs)) >= 3            # genuinely different values
    assert probs[0] > probs[-1]            # more natural mix -> lower spoof


def test_features_shape():
    f = _features(_synthetic(1), SR)
    for k in ["duration_s", "sample_rate", "silence_ratio", "noise_floor", "centroid_cv", "rms_cv"]:
        assert k in f
