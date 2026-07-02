"""URL extraction, normalization, and lexical risk features."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import tldextract

from ..registry import official_domains
from ..schemas import LinkInfo

_URL_RE = re.compile(
    r"""(?xi)\b(
        (?:https?://|www\.)
        [^\s<>"'\)\]]+
    )""",
)

_BRAND_TOKENS = [
    "sebi", "nse", "bse", "nsdl", "cdsl", "rbi", "amfi",
    "zerodha", "groww", "angelone", "icicidirect", "kite",
]

_SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "link", "live", "online", "site", "info",
    "buzz", "rest", "gq", "cf", "tk", "ml", "work", "support", "verify",
}

_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "rebrand.ly", "cutt.ly",
    "is.gd", "ow.ly", "shorturl.at", "rb.gy",
}

_SENSITIVE_PATH = re.compile(
    r"(login|signin|verify|kyc|otp|password|wallet|payment|redeem|claim|update-account|net-?banking)",
    re.I,
)


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(1).rstrip(".,);]'\"")
        if u.lower().startswith("www."):
            u = "http://" + u
        if u not in urls:
            urls.append(u)
    return urls


def _registered_domain(url: str) -> tuple[str, str]:
    ext = tldextract.extract(url)
    host = ".".join(p for p in [ext.subdomain, ext.domain, ext.suffix] if p)
    reg = ".".join(p for p in [ext.domain, ext.suffix] if p)
    return host.lower(), reg.lower()


def analyze_url(url: str) -> LinkInfo:
    host, reg = _registered_domain(url)
    parsed = urlparse(url if "://" in url else "http://" + url)
    info = LinkInfo(raw=url, domain=host, registered_domain=reg)

    officials = official_domains()
    if host in officials or reg in officials:
        info.allowlisted = True
        info.reasons.append("Domain is on the official-source allowlist")
        return info

    reasons: list[str] = []

    hay = f"{host}"
    for tok in _BRAND_TOKENS:
        if tok in hay:
            reasons.append(f"Contains official brand token '{tok}' but domain is not official")
            break

    suffix = reg.split(".")[-1] if "." in reg else ""
    if suffix in _SUSPICIOUS_TLDS:
        reasons.append(f"Uncommon / low-trust TLD '.{suffix}'")

    if reg in _SHORTENERS:
        reasons.append("Link shortener conceals the true destination")

    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        reasons.append("Uses a raw IP address instead of a domain")

    if _SENSITIVE_PATH.search(parsed.path + "?" + (parsed.query or "")):
        reasons.append("Path targets credentials/OTP/payment capture")

    if host.count("-") >= 3:
        reasons.append("Domain uses many hyphens (obfuscation pattern)")
    if len(host) > 40:
        reasons.append("Unusually long hostname")

    if "xn--" in host:
        reasons.append("Punycode domain — possible homoglyph impersonation")

    info.reasons = reasons
    info.suspicious = bool(reasons)
    return info


def analyze_links(text_or_url: str) -> list[LinkInfo]:
    urls = extract_urls(text_or_url)
    if not urls:
        candidate = text_or_url.strip()
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", candidate, re.I):
            urls = [candidate]
    return [analyze_url(u) for u in urls]
