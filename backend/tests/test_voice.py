"""Voice detector tests — LFCC + signal feature scoring."""
import numpy as np

from app.detectors.voice import _compute_spoof_indicators, _fuse_score, _spoof_type


def _mock_signal(pitch_cv=0.15, energy_cv=0.3, flatness=0.1, zcr=0.05, mfcc_std=10.0):
    return {
        "pitch": np.random.normal(200, 200 * pitch_cv, 100).clip(50, 400),
        "energy": np.random.normal(0.1, 0.1 * energy_cv, 50).clip(0.001, 1),
        "spectral_flatness": np.full(50, flatness),
        "spectral_centroid": np.random.normal(2000, 500, 50),
        "zcr": np.full(50, zcr),
        "mfcc": np.random.normal(0, mfcc_std, (40, 100)),
        "is_silent": False,
    }


def test_synthetic_indicators_high():
    sig = _mock_signal(pitch_cv=0.03, energy_cv=0.08, flatness=0.5)
    ind = _compute_spoof_indicators(sig)
    assert ind["auxiliary_score"] >= 0.5
    assert len(ind["flags"]) >= 2


def test_natural_indicators_low():
    sig = _mock_signal(pitch_cv=0.3, energy_cv=0.5, flatness=0.05, zcr=0.03, mfcc_std=15)
    ind = _compute_spoof_indicators(sig)
    assert ind["auxiliary_score"] <= 0.3
    assert len(ind["flags"]) <= 1


def test_fuse_score_range():
    assert 0.0 <= _fuse_score(0.0, 0.0) <= 1.0
    assert 0.0 <= _fuse_score(1.0, 1.0) <= 1.0
    assert _fuse_score(0.9, 0.0) > _fuse_score(0.1, 0.0)


def test_spoof_type_labels():
    assert _spoof_type(0.2, [], {}) == "GENUINE"
    assert _spoof_type(0.9, ["High spectral flatness"], {"spectral_flatness": 0.5}) in ("AI_DEEPFAKE", "VOICE_CONVERSION")
    assert _spoof_type(0.6, [], {"energy_variation": 0.05}) == "REPLAY_ATTACK"
    assert _spoof_type(0.7, [], {"pitch_variation": 0.03}) == "TTS_SYNTHETIC"
