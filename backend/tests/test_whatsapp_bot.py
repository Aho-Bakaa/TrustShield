"""WhatsApp bot module tests: signature verification + retry queue (roadmap 3.1)."""
import hashlib
import hmac
import json
import time

import app.whatsapp_bot as wb
from app.config import get_settings
import app.config as _cfg


def _with_whatsapp_config():
    """Patch settings so the webhook is 'enabled' with a known verify token."""
    s = get_settings()
    original = (s.whatsapp_verify_token, s.whatsapp_access_token, s.whatsapp_phone_number_id)
    s.whatsapp_verify_token = "testsecret"
    s.whatsapp_access_token = "testtoken"
    s.whatsapp_phone_number_id = "testphone"
    return original


def test_verify_signature_accepts_valid():
    orig = _with_whatsapp_config()
    try:
        body = b'{"entry": []}'
        sig = "sha256=" + hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
        assert wb.verify_signature(body, sig) is True
    finally:
        _cfg.get_settings().whatsapp_verify_token = orig[0]


def test_verify_signature_rejects_bad():
    orig = _with_whatsapp_config()
    try:
        body = b'{"entry": []}'
        assert wb.verify_signature(body, "sha256=deadbeef") is False
        assert wb.verify_signature(body, None) is False
        assert wb.verify_signature(body, "sha1=abc") is False
    finally:
        _cfg.get_settings().whatsapp_verify_token = orig[0]


def test_pending_queue_round_trip_and_retry():
    # Enqueue -> flush when backoff hasn't elapsed should send 0 (mocked _reply_text).
    orig = _with_whatsapp_config()
    try:
        wb._PENDING_FILE = "test_whatsapp_pending.json"
        # Clear any leftover file.
        wb._pending_save([])

        wb._pending_enqueue("pid", "12345", "hello")
        assert len(wb._pending_load()) == 1

        # Make it due immediately, force reply failure -> flush keeps it queued and bumps attempts.
        items = wb._pending_load()
        for it in items:
            it["next_attempt"] = 0
        wb._pending_save(items)
        wb._reply_text = lambda *a, **k: False
        sent = wb.flush_pending()
        assert sent == 0
        items = wb._pending_load()
        assert len(items) == 1
        assert items[0]["attempts"] >= 1

        # Force reply success -> flush sends it and empties the queue.
        wb._reply_text = lambda *a, **k: True
        items = wb._pending_load()
        for it in items:
            it["next_attempt"] = 0  # make it due immediately
        wb._pending_save(items)
        sent = wb.flush_pending()
        assert sent == 1
        assert wb._pending_load() == []

        wb._pending_save([])
    finally:
        _cfg.get_settings().whatsapp_verify_token = orig[0]
