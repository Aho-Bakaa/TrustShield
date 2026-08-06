"""Intake layer: classify the channel and normalize into an AnalysisRequest."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .preprocessing.entities import extract_entities
from .preprocessing.urls import analyze_links, extract_urls
from .schemas import AnalysisRequest, ChannelType

_SOCIAL_HOSTS = {
    "twitter.com", "x.com", "facebook.com", "fb.com", "instagram.com",
    "t.me", "telegram.me", "youtube.com", "youtu.be", "reddit.com",
    "linkedin.com", "threads.net", "whatsapp.com", "chat.whatsapp.com",
}

_EMAIL_MARKERS = re.compile(
    r"(^|\n)\s*(from|subject|to|dear|reply-to|sent)\s*[:>]",
    re.I,
)


def _is_bare_url(text: str) -> bool:
    t = text.strip()
    if " " in t or "\n" in t:
        return False
    return bool(re.match(r"^(https?://|www\.)?[\w.-]+\.[a-z]{2,}(/|\?|#|$)", t, re.I))


def _host_of(url: str) -> str:
    u = url if "://" in url else "http://" + url
    return (urlparse(u).hostname or "").lower().lstrip("www.")


# Key phrases that suggest this input is a securities-market communication.
# If none of these match, the input is likely irrelevant.
_SECURITIES_MARKERS = re.compile(
    r"\b(sebi|rbi|nse|bse|nsdl|cdsl|demat|kyc|otp|password|upi|"
    r"ipo|mutual fund|broker|zerodha|groww|angel one|upstox|"
    r"cams|kfintech|scores|investor|share(s)?|dividend|bonus|"
    r"stock|trading|portfolio|holding(s)?|folio|nominee|"
    r"fraud|scam|phish(ing)?|suspended|frozen|verify|urgent|"
    r"5paisa|icici direct|hdfc securities|paytm money|mstock|"
    r"securities|exchange|regulator(y)?)\b",
    re.I,
)

_QUERY_MARKERS = re.compile(
    r"\?\s*$|^(?:is|are|was|were|will|would|can|could|should|has|have|did|do|does|what|why|how|who|when|where)\b|\?\?+",
    re.I,
)
_HEADLINE_MARKERS = re.compile(
    r"^(?:BREAKING|JUST IN|UPDATE|ALERT|RUMOUR|RUMOR|NEWS)\b",
    re.I,
)


def is_relevant(text: str, entities: list) -> bool:
    """Return True if the input contains at least one securities-market signal."""
    if not text or not text.strip():
        return False
    if entities:
        return True
    urls = extract_urls(text)
    if urls:
        return True  # always check links — could be a phishing URL
    if _SECURITIES_MARKERS.search(text):
        return True
    return False


def classify_channel(text: str, has_audio: bool, hint: ChannelType | None) -> ChannelType:
    if has_audio:
        return ChannelType.AUDIO
    if hint and hint != ChannelType.UNKNOWN:
        return hint

    text = (text or "").strip()
    if not text:
        return ChannelType.UNKNOWN

    urls = extract_urls(text) or ([text] if _is_bare_url(text) else [])
    social = any(
        any(h == host or host.endswith("." + h) for h in _SOCIAL_HOSTS)
        for host in (_host_of(u) for u in urls)
    )
    if social:
        return ChannelType.SOCIAL

    if urls and len(text) <= max(len(urls[0]) + 15, 90):
        return ChannelType.URL

    if _EMAIL_MARKERS.search(text):
        return ChannelType.EMAIL

    if _QUERY_MARKERS.search(text) and len(text) < 300:
        return ChannelType.QUERY

    if _HEADLINE_MARKERS.search(text) and not urls:
        return ChannelType.QUERY

    if len(text) > 90:
        return ChannelType.EMAIL

    if urls:
        return ChannelType.URL

    if len(text) < 120 and ("?" in text or text.count("?") >= 2):
        return ChannelType.QUERY

    return ChannelType.QUERY


def build_request(
    *,
    text: str = "",
    audio_path: str | None = None,
    channel_hint: ChannelType | None = None,
    claimed_source: str | None = None,
    timestamp: str | None = None,
    original_filename: str | None = None,
) -> AnalysisRequest:
    channel = classify_channel(text, bool(audio_path), channel_hint)
    links = analyze_links(text) if text else []
    entities = extract_entities(text) if text else []

    meta = {}
    if original_filename:
        meta["filename"] = original_filename

    return AnalysisRequest(
        channel_type=channel,
        raw_input=text or "",
        claimed_source=claimed_source,
        links=links,
        entities=entities,
        audio_path=audio_path,
        attachments=[audio_path] if audio_path else [],
        timestamp=timestamp,
        meta=meta,
    )
