"""WhatsApp bot (roadmap 3.1).

Meta WhatsApp Cloud API webhook handler. A user forwards a suspicious message
to the TrustShield WhatsApp number; this replies with a verdict.

Flow:
  1. GET  /api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=...  -> echo hub.challenge
  2. POST /api/whatsapp/webhook  -> message payload -> analyze -> reply via Messages API

Config (empty = disabled, webhook returns 403):
  WHATSAPP_VERIFY_TOKEN    shared secret for the subscribe handshake
  WHATSAPP_ACCESS_TOKEN    Meta Graph API token
  WHATSAPP_PHONE_NUMBER_ID the sender phone number ID

The analysis runs in a threadpool via `fusion.analyze` and the reply is sent
with a short httpx POST. No reply is attempted if credentials are missing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from .config import get_settings
from .fusion import analyze
from .intake import build_request
from .log import get_logger

_log = get_logger("whatsapp")

_GRAPH_URL = "https://graph.facebook.com/v19.0"

# Pending replies awaiting a successful send (persisted so nothing is lost).
_PENDING_FILE = "whatsapp_pending.json"
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 30


def webhook_enabled() -> bool:
    s = get_settings()
    return bool(s.whatsapp_verify_token and s.whatsapp_access_token and s.whatsapp_phone_number_id)


def verify_hub(params: dict[str, str]) -> str | None:
    """Return the hub.challenge if the subscribe handshake validates."""
    s = get_settings()
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token and s.whatsapp_verify_token and token == s.whatsapp_verify_token:
        return challenge
    return None


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate Meta's X-Hub-Signature-256 HMAC-SHA256 of the raw body.

    Meta signs the raw request body with the app secret (the WhatsApp
    verify token in our setup). Reject any request that doesn't match.
    """
    s = get_settings()
    secret = s.whatsapp_verify_token
    if not secret:
        return False
    if not signature_header:
        return False
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header[len(prefix):], expected)


def _extract_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull (phone_number_id, from, text) tuples out of a Meta webhook payload."""
    out: list[dict[str, Any]] = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        continue
                    out.append({
                        "phone_number_id": phone_number_id,
                        "from": msg.get("from", ""),
                        "text": (msg.get("text", {}) or {}).get("body", ""),
                        "message_id": msg.get("id", ""),
                    })
    except Exception as exc:
        _log.warning("whatsapp payload parse failed: %s", str(exc)[:120])
    return out


def _pending_load() -> list[dict[str, Any]]:
    try:
        with open(_PENDING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as exc:
        _log.warning("pending load failed: %s", str(exc)[:100])
        return []


def _pending_save(items: list[dict[str, Any]]) -> None:
    try:
        with open(_PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f)
    except Exception as exc:
        _log.warning("pending save failed: %s", str(exc)[:100])


def _pending_enqueue(phone_number_id: str, to: str, text: str) -> None:
    items = _pending_load()
    items.append({
        "phone_number_id": phone_number_id,
        "to": to,
        "text": text[:4000],
        "attempts": 0,
        "next_attempt": time.time() + _RETRY_BACKOFF_SECONDS,
        "created_at": time.time(),
    })
    _pending_save(items)


def flush_pending() -> int:
    """Attempt to send queued replies whose backoff has elapsed. Returns sent count."""
    items = _pending_load()
    if not items:
        return 0
    now = time.time()
    kept: list[dict[str, Any]] = []
    sent = 0
    for item in items:
        if item.get("next_attempt", 0) > now:
            kept.append(item)
            continue
        if item.get("attempts", 0) >= _MAX_RETRIES:
            _log.warning("dropping pending whatsapp reply after %d attempts (to=%s)", _MAX_RETRIES, item.get("to"))
            continue
        if _reply_text(item.get("phone_number_id", ""), item.get("to", ""), item.get("text", "")):
            sent += 1
            continue
        item["attempts"] = item.get("attempts", 0) + 1
        item["next_attempt"] = now + _RETRY_BACKOFF_SECONDS * (2 ** item["attempts"])
        kept.append(item)
    _pending_save(kept)
    return sent


def _reply_text(phone_number_id: str, to: str, text: str, timeout: float = 8.0) -> bool:
    s = get_settings()
    if not (s.whatsapp_access_token and phone_number_id):
        return False
    url = f"{_GRAPH_URL}/{phone_number_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4000]},
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=body, headers={
                "Authorization": f"Bearer {s.whatsapp_access_token}",
                "Content-Type": "application/json",
            })
        ok = resp.status_code in (200, 201)
        if not ok:
            _log.warning("whatsapp reply failed status=%s body=%s", resp.status_code, resp.text[:200])
        return ok
    except Exception as exc:
        _log.warning("whatsapp reply error: %s", str(exc)[:150])
        return False


def _verdict_text(result: Any) -> str:
    level = result.risk_level.value.upper()
    return (
        f"TrustShield: {level} risk ({result.risk_score}/100).\n\n"
        f"{result.threat_label}\n\n"
        f"{result.summary[:280]}\n\n"
        f"Action: {result.recommended_action[:240]}"
    )


def handle_webhook(payload: dict[str, Any]) -> int:
    """Process a Meta WhatsApp webhook POST. Returns HTTP status for the response."""
    if not webhook_enabled():
        return 403

    messages = _extract_messages(payload)
    if not messages:
        # Acknowledge the delivery/status update immediately.
        return 200

    for msg in messages:
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        if len(text) > 4000:
            text = text[:4000]

        t0 = time.time()
        req = build_request(text=text, channel_hint=None)
        try:
            result = analyze(req)
            reply = _verdict_text(result)
            _log.info("whatsapp analyzed msg=%s risk=%s %dms", msg.get("message_id"),
                      result.risk_level.value, int((time.time() - t0) * 1000))
        except Exception as exc:
            _log.warning("whatsapp analyze failed: %s", str(exc)[:150])
            reply = "TrustShield couldn't analyze that message right now. Please try again."

        # Send now; on failure queue it for the retry flush so nothing is lost.
        if not _reply_text(msg.get("phone_number_id", ""), msg.get("from", ""), reply):
            _pending_enqueue(msg.get("phone_number_id", ""), msg.get("from", ""), reply)

    # 200 so Meta doesn't retry the webhook.
    return 200


def status() -> dict[str, Any]:
    s = get_settings()
    return {
        "enabled": webhook_enabled(),
        "verify_token_set": bool(s.whatsapp_verify_token),
        "access_token_set": bool(s.whatsapp_access_token),
        "phone_number_id_set": bool(s.whatsapp_phone_number_id),
        "endpoint": "/api/whatsapp/webhook",
    }
