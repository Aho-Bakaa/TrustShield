"""Unit tests for URL features, entity extraction, and manipulation heuristics."""
from app.preprocessing import heuristics
from app.preprocessing.entities import extract_entities, max_criticality
from app.preprocessing.urls import analyze_url, extract_urls


def test_official_domain_allowlisted():
    info = analyze_url("https://www.sebi.gov.in/investors.html")
    assert info.allowlisted is True
    assert info.suspicious is False


def test_brand_token_impersonation_flagged():
    info = analyze_url("http://sebi-kyc-verify.xyz/login")
    assert info.allowlisted is False
    assert info.suspicious is True
    assert any("brand token" in r for r in info.reasons)
    assert any("TLD" in r for r in info.reasons)  # .xyz


def test_credential_path_and_ip_flagged():
    info = analyze_url("http://192.168.10.5/nse-kyc/update-account")
    assert info.suspicious is True
    assert any("IP address" in r for r in info.reasons)


def test_shortener_flagged():
    info = analyze_url("https://bit.ly/sebi-refund")
    assert info.suspicious is True
    assert any("shortener" in r.lower() for r in info.reasons)


def test_extract_urls_multiple():
    urls = extract_urls("see http://a.com and www.b.co/x plus https://c.io")
    assert len(urls) == 3


def test_entities_and_criticality():
    ents = extract_entities("This is an official SEBI notice about NSE and Zerodha.")
    names = {e.text for e in ents}
    assert "SEBI" in names and "NSE" in names and "Zerodha" in names
    assert max_criticality(ents) == 1.0  # SEBI


def test_heuristics_fire_on_phishing_text():
    res = heuristics.scan("URGENT: share your OTP and password immediately or account suspended")
    assert res["score"] > 0
    assert "urgency" in res["categories"]
    assert "credential_request" in res["categories"]


def test_heuristics_quiet_on_benign_text():
    res = heuristics.scan("Markets closed higher today; this is general commentary only.")
    assert res["score"] == 0
    assert res["fired"] == []
