"""Claim cache tests (roadmap 2.3)."""
import time

from app.data.claim_cache import clear_expired, get_cached, set_cached


def test_cache_round_trip():
    set_cached("SEBI has banned retail investors", {"status": "verified", "summary": "Confirmed."})
    hit = get_cached("SEBI has banned retail investors")
    assert hit is not None
    assert hit["status"] == "verified"


def test_cache_normalizes_case_and_whitespace():
    set_cached("SEBI bans pump and dump", {"status": "verified"})
    assert get_cached("  sebi BANS Pump   and dump ") is not None


def test_cache_miss_returns_none():
    assert get_cached("completely unrelated claim never cached") is None


def test_cache_expiry():
    set_cached("expiring claim", {"status": "verified"}, ttl_seconds=-1)
    assert get_cached("expiring claim") is None
    assert clear_expired() >= 0
