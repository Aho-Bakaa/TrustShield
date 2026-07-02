"""Trust-fusion tests (deterministic: rule-based LLM, no network)."""
from app.fusion import analyze
from app.intake import build_request
from app.schemas import ChannelType, RiskLevel


def _analyze(text, **kw):
    return analyze(build_request(text=text, **kw))


def test_verified_official_is_low_risk():
    r = _analyze(
        "SEBI Investor Charter update at https://www.sebi.gov.in/investor-charter.html dkim=pass",
        claimed_source="SEBI",
    )
    assert r.risk_level == RiskLevel.LOW
    assert r.authenticity.is_official_source is True
    assert "Verified" in r.threat_label


def test_phishing_email_flagged_and_escalated():
    r = _analyze(
        "URGENT: SEBI KYC suspended. Share OTP and password at http://sebi-kyc-verify.xyz/login within 24 hours",
        claimed_source="SEBI",
    )
    assert r.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
    assert r.escalated is True
    assert r.risk_score > 0


def test_benign_message_low_risk():
    r = _analyze("Reminder: markets close early today. General information only, not advice.")
    assert r.risk_level == RiskLevel.LOW


def test_high_criticality_entity_raises_severity():
    # SEBI (criticality 1.0) + suspicious link should reach HIGH more readily.
    r = _analyze(
        "SEBI account suspended, verify at http://sebi-verify.top/kyc immediately or lose access",
        claimed_source="SEBI",
    )
    assert r.risk_level == RiskLevel.HIGH


def test_result_has_trace_and_evidence():
    r = _analyze("guaranteed 200% returns join telegram http://tips.top now urgent")
    assert len(r.trace) >= 3
    assert len(r.evidence) >= 1
    assert r.id and r.created_at


def test_scores_are_not_constant():
    """Different malicious inputs should not all collapse to one hardcoded number."""
    a = _analyze("URGENT share OTP password at http://sebi-kyc.xyz/login", claimed_source="SEBI").risk_score
    b = _analyze("join telegram tips http://tips.top", ).risk_score
    c = _analyze("pre-IPO guaranteed 300% pay fee http://ipo-alloc.top/pay", claimed_source="NSE").risk_score
    assert len({a, b, c}) >= 2  # at least some variation
