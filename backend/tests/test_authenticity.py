"""Authenticity-layer tests."""
from app.detectors.authenticity import assess
from app.intake import build_request


def test_official_source_verified():
    req = build_request(
        text="SEBI notice: read at https://www.sebi.gov.in/investor-charter.html dkim=pass",
        claimed_source="SEBI",
    )
    a = assess(req)
    assert a.is_official_source is True
    assert a.official_confidence >= 0.8
    assert a.provenance_available is True  # dkim=pass


def test_claimed_official_but_offdomain_not_verified():
    req = build_request(
        text="SEBI: verify KYC at http://sebi-kyc-verify.xyz/login",
        claimed_source="SEBI",
    )
    a = assess(req)
    assert a.is_official_source is False
    assert a.official_confidence <= 0.1
    assert any("NOT verified" in s for s in a.signals)


def test_no_official_source():
    req = build_request(text="join my telegram for tips http://random-tips.top")
    a = assess(req)
    assert a.is_official_source is False
