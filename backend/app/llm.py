"""Provider-agnostic reasoning layer.

Wraps LiteLLM for Groq (default), OpenRouter, or Gemini. Provider errors
trigger retries with fallback providers. When no provider is available,
returns a neutral assessment — never fabricates a false analysis.

Robustness notes:
  - gpt-oss reasoning models on Groq reject strict `json_object` mode
    intermittently, so for them we prompt for JSON and parse it ourselves.
  - Any provider error triggers one retry without `response_format` before
    falling back to an alternate provider or neutral response.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from .config import get_settings
from .log import get_logger

_log = get_logger("llm")
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

STATS: dict[str, Any] = {"calls": 0, "live": 0, "neutral": 0, "last_error": None, "last_latency_ms": 0}


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = _THINK.sub("", text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def _is_reasoning_model(model: str) -> bool:
    m = model.lower()
    return "gpt-oss" in m or "o1" in m or "o3" in m or "reason" in m or "deepseek-r" in m


def _call(messages: list[dict], *, use_response_format: bool) -> str:
    import litellm  # lazy import so the app boots without the package
    import time

    settings = get_settings()
    litellm.drop_params = True  # silently drop params a provider doesn't accept
    kwargs: dict[str, Any] = dict(
        model=settings.resolved_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )
    if _is_reasoning_model(settings.resolved_model):
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort
    elif use_response_format:
        kwargs["response_format"] = {"type": "json_object"}

    t = time.time()
    resp = litellm.completion(**kwargs)
    STATS["last_latency_ms"] = int((time.time() - t) * 1000)
    return resp.choices[0].message.content or ""


def reason_json(
    system: str,
    user: str,
    neutral: Callable[[], dict[str, Any]] | dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Ask the LLM for a JSON object. Returns (data, used_llm).

    `neutral` is a dict (or callable) returned when no LLM is available.
    This is the honest "cannot analyze" assessment — never a fabricated score.
    """
    settings = get_settings()

    def _neutral() -> dict[str, Any]:
        return neutral() if callable(neutral) else dict(neutral)

    if not settings.llm_available:
        STATS["neutral"] += 1
        return _neutral(), False

    STATS["calls"] += 1
    messages = [
        {"role": "system", "content": system + "\nRespond ONLY with a single JSON object. No prose, no markdown."},
        {"role": "user", "content": user},
    ]

    for use_rf in (True, False):
        try:
            content = _call(messages, use_response_format=use_rf)
            data = _extract_json(content)
            if data:
                STATS["live"] += 1
                STATS["last_error"] = None
                _log.info("%s live %dms (rf=%s)", settings.resolved_model, STATS["last_latency_ms"], use_rf)
                return data, True
        except Exception as exc:
            STATS["last_error"] = str(exc)[:200]
            _log.warning("LLM call failed (rf=%s): %s", use_rf, str(exc)[:120])
            continue

    STATS["neutral"] += 1
    _log.warning("%s unavailable — returning neutral assessment", settings.resolved_model)
    data = _neutral()
    if STATS["last_error"]:
        data.setdefault("_llm_error", STATS["last_error"])
    return data, False


_VISION_PROMPT = (
    "You are analyzing a SCREENSHOT submitted for securities-market fraud review "
    "(it may be a WhatsApp/Telegram message, an email, a trading-app page, or a social post). "
    "1) Transcribe ALL visible text verbatim. 2) Note any URLs, phone numbers, or UPI IDs. "
    "3) Describe in one line what the screenshot is. "
    "Respond ONLY as JSON: {\"transcript\": string, \"description\": string, \"urls\": [string]}."
)


_SCREENSHOT_SYS = (
    "You are viewing a SCREENSHOT of a web page a user was directed to from a securities-market "
    "message. Judge what the page is and whether it deceptively imitates a known brand "
    "(SEBI, NSE, BSE, RBI, CDSL, NSDL, or a broker like Zerodha/Groww/Angel One). "
    "A genuine login page on a brand's REAL domain is NOT deceptive. "
    "Respond ONLY as JSON: {\"page_type\": string, \"imitates_brand\": string_or_null, "
    "\"is_login_or_payment\": bool, \"looks_deceptive\": bool, \"notes\": string (<=40 words)}."
)


def _vision_completion(prompt_text: str, image_b64: str, mime: str, max_tokens: int) -> str:
    import litellm
    import time

    settings = get_settings()
    litellm.drop_params = True
    data_url = f"data:{mime};base64,{image_b64}"
    t = time.time()
    resp = litellm.completion(
        model=settings.llm_vision_model,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
        max_tokens=max_tokens,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
    )
    STATS["last_latency_ms"] = int((time.time() - t) * 1000)
    return resp.choices[0].message.content or ""


def describe_image(image_bytes: bytes, mime: str = "image/png") -> tuple[dict[str, Any], bool]:
    """Extract text + a description from a screenshot via the vision model.

    Returns ({transcript, description, urls}, used_vision).
    """
    import base64

    settings = get_settings()
    if not settings.vision_available:
        _log.warning("vision requested but %s has no key configured", settings.llm_vision_model)
        return {"transcript": "", "description": "", "urls": [], "_note": "vision model not configured"}, False
    try:
        content = _vision_completion(_VISION_PROMPT, base64.b64encode(image_bytes).decode(), mime, 900)
        data = _extract_json(content) or {"transcript": content.strip(), "description": "", "urls": []}
        _log.info("vision(describe) %s %dms transcript_len=%d",
                  settings.llm_vision_model, STATS["last_latency_ms"], len(data.get("transcript", "")))
        return data, True
    except Exception as exc:
        _log.warning("vision describe failed: %s", str(exc)[:150])
        return {"transcript": "", "description": "", "urls": [], "_note": str(exc)[:150]}, False


def analyze_screenshot(screenshot_b64: str) -> tuple[dict[str, Any], bool]:
    """Ask the vision model to assess a rendered-page screenshot for brand imitation."""
    settings = get_settings()
    if not settings.vision_available or not screenshot_b64:
        return {}, False
    try:
        content = _vision_completion(_SCREENSHOT_SYS, screenshot_b64, "image/png", 400)
        data = _extract_json(content) or {"page_type": "unknown", "notes": content.strip()}
        _log.info("vision(screenshot) %dms", STATS["last_latency_ms"])
        return data, True
    except Exception as exc:
        _log.warning("screenshot analysis failed: %s", str(exc)[:150])
        return {}, False


def analyze_email_screenshot(image_bytes: bytes, mime: str = "image/png") -> tuple[dict[str, Any], bool]:
    """Analyze an email screenshot — extract sender, body, URLs, layout signals."""
    import base64
    from .prompts import load as load_prompt

    settings = get_settings()
    if not settings.vision_available or not image_bytes:
        return {}, False
    try:
        content = _vision_completion(
            load_prompt("email_screenshot.txt"),
            base64.b64encode(image_bytes).decode(), mime, 1200)
        data = _extract_json(content) or {"body_text": content.strip(), "urls": [], "notes": "JSON parse failed"}
        _log.info("vision(email_screenshot) %dms", STATS["last_latency_ms"])
        return data, True
    except Exception as exc:
        _log.warning("email screenshot analysis failed: %s", str(exc)[:150])
        return {}, False
    """Ask the vision model to assess a rendered-page screenshot for brand imitation."""
    settings = get_settings()
    if not settings.vision_available or not screenshot_b64:
        return {}, False
    try:
        content = _vision_completion(_SCREENSHOT_SYS, screenshot_b64, "image/png", 400)
        data = _extract_json(content)
        _log.info("vision(page) %s %dms imitates=%s deceptive=%s",
                  settings.llm_vision_model, STATS["last_latency_ms"],
                  data.get("imitates_brand"), data.get("looks_deceptive"))
        return data, bool(data)
    except Exception as exc:
        _log.warning("vision page-analysis failed: %s", str(exc)[:150])
        return {}, False


def llm_status() -> dict[str, Any]:
    s = get_settings()
    return {
        "provider": s.llm_provider,
        "model": s.resolved_model,
        "available": s.llm_available,
        "reasoning_effort": s.llm_reasoning_effort,
        "mode": "live" if s.llm_available else "no provider key configured",
        "vision_model": s.llm_vision_model,
        "vision_available": s.vision_available,
        "stats": dict(STATS),
    }
