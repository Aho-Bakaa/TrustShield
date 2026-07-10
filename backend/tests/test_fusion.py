"""Trust-fusion tests (no LLM — neutral assessments only)."""
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


def test_phishing_text_flagged_and_escalated():
    r = _analyze(
        "URGENT: SEBI KYC suspended. Share OTP and password at http://sebi-kyc-verify.xyz/login within 24 hours",
        claimed_source="SEBI",
    )
    assert r.escalated is True
    assert r.risk_score > 0


def test_benign_message_has_trace_and_evidence():
    r = _analyze("Reminder: markets close early today. General information only, not advice.")
    assert len(r.trace) >= 3
    assert len(r.evidence) >= 1
    assert r.id and r.created_at


def test_high_criticality_entity_present():
    r = _analyze(
        "SEBI account suspended, verify at http://sebi-verify.top/kyc immediately or lose access",
        claimed_source="SEBI",
    )
    sebi_entities = [e for e in r.entities if e.text == "SEBI"]
    assert len(sebi_entities) >= 1
    assert sebi_entities[0].criticality >= 0.9


def test_result_has_trace_and_evidence():
    r = _analyze("guaranteed 200% returns join telegram http://tips.top now urgent")
    assert len(r.trace) >= 3
    assert len(r.evidence) >= 1
    assert r.id and r.created_at


def test_allowlisted_link_recognized():
    r = _analyze("Visit us at https://www.sebi.gov.in")
    assert r.authenticity.is_official_source is True
    assert r.authenticity.official_confidence >= 0.8
    assert r.risk_level == RiskLevel.LOW
