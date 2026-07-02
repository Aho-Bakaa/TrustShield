"""Rendering / evidence-extraction tests.

Two layers:
  1. `_analyze_html` on fixture files — pure, deterministic, always runs.
  2. Real Playwright rendering of file:// fixtures — skipped if Chromium absent.
"""
from pathlib import Path

import pytest

from app.render import _analyze_html

FIX = Path(__file__).resolve().parent.parent / "app" / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_credential_form_detected_in_fake_kyc():
    data = _analyze_html(_read("fake-sebi-kyc.html"), "http://x/fake-sebi-kyc.html")
    assert data["has_login_form"] is True
    assert data["captures_sensitive"] is True
    assert "SEBI" in (data["title"] or "")


def test_payment_form_detected_in_ipo_page():
    data = _analyze_html(_read("fake-ipo-payment.html"), "http://x/ipo")
    assert data["captures_sensitive"] is True  # upi/card/cvv


def test_benign_page_has_no_capture():
    data = _analyze_html(_read("official-notice.html"), "http://x/notice")
    assert data["has_login_form"] is False
    assert data["captures_sensitive"] is False


def _playwright_ok():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _playwright_ok(), reason="Playwright/Chromium not available")
def test_playwright_renders_fixture():
    from app.render import _render_playwright

    uri = (FIX / "fake-sebi-kyc.html").as_uri()
    data = _render_playwright(uri, True)
    assert data["rendered"] is True
    assert data["method"] == "playwright"
    assert data["captures_sensitive"] is True
    assert "SEBI" in (data["title"] or "")
