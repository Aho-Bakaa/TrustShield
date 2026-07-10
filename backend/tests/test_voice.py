"""Voice detector tests — feature-driven spoof scoring."""
import numpy as np

from app.detectors.voice import _load_audio, _spectral_features, _score_spoof
from eval.make_demo_audio import SR, _natural, _synthetic


def _prob(sig):
    spectral = _spectral_features(sig, SR)
    pitch = {}
    mfcc = np.zeros((13, 3))
    return _score_spoof(spectral, pitch, mfcc)[0]


def test_synthetic_scored_realistically():
    assert 0.0 <= _prob(_synthetic(1)) <= 1.0


def test_natural_scored_realistically():
    assert 0.0 <= _prob(_natural(1)) <= 1.0


def test_score_is_continuous():
    syn, nat = _synthetic(1), _natural(1)
    n = min(len(syn), len(nat))
    probs = []
    for a in (0.0, 0.35, 0.7, 1.0):
        mix = (1 - a) * syn[:n] + a * nat[:n]
        probs.append(round(_prob(mix), 3))
    assert len(set(probs)) >= 2


def test_spectral_features_shape():
    f = _spectral_features(_synthetic(1), SR)
    for k in ["centroid_mean", "centroid_cv", "flatness_mean", "zcr_mean", "rms_mean"]:
        assert k in f
