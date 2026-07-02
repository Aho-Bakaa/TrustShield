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

    if _EMAIL_MARKERS.search(text) or len(text) > 90:
        return ChannelType.EMAIL

    if urls:
        return ChannelType.URL
    return ChannelType.EMAIL  # default: treat pasted message text as email/message


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
