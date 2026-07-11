"""Web search engine for claim verification.

Uses DuckDuckGo Lite (HTML table layout) for reliable, no-API-key search.

Classification:
- verified: official source or ≥2 reputable sources confirm the claim
- contradicted: official source explicitly denies/refutes the claim
- unverified: results exist but don't confirm or deny
- not_found: zero results returned (NOT contradicted)
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import get_settings
from .log import get_logger

_log = get_logger("search")

_OFFICIAL = {"sebi.gov.in", "rbi.org.in", "nseindia.com", "bseindia.com",
             "scores.sebi.gov.in", "nsdl.co.in", "cdslindia.com", "amfiindia.com"}
_NEWS = {"moneycontrol.com", "economictimes.indiatimes.com", "livemint.com",
         "bloombergquint.com", "businesstoday.in", "thehindubusinessline.com",
         "cnbctv18.com", "ndtvprofit.com"}

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_DENIAL_RE = re.compile(r"denied|refuted|fake|false|hoax|not issued|did not issue|no such|fraudulent|scam", re.I)


def _search_ddg(query: str, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Search via DuckDuckGo Lite (HTML table layout, no JS needed)."""
    url = "https://lite.duckduckgo.com/lite/"
    try:
        with httpx.Client(headers={"User-Agent": _UA}, timeout=timeout, follow_redirects=True) as client:
            resp = client.post(url, data={"q": query[:120]})
            if resp.status_code != 200:
                return []
    except Exception as exc:
        _log.debug("ddg lite failed: %s", str(exc)[:80])
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    tds = soup.select("td")
    results = []

    i = 0
    while i < len(tds) - 6:
        text = tds[i].get_text(strip=True)
        if re.match(r"^\d+\.$", text):
            title_td = tds[i + 1]
            snippet_td = tds[i + 3]
            url_td = tds[i + 5]

            a = title_td.select_one("a")
            title = (a.get_text(strip=True) if a else title_td.get_text(strip=True))[:120]
            href = ""
            if a and a.get("href"):
                href = a["href"]
            elif url_td.get_text(strip=True):
                url_text = url_td.get_text(strip=True)
                if url_text.startswith("http"):
                    href = url_text
                elif "." in url_text:
                    href = "https://" + url_text

            domain = (urlparse(href).hostname or "").lower().lstrip("www.") if href else ""
            snippet = snippet_td.get_text(strip=True)[:200]

            if title and domain:
                results.append({
                    "title": title,
                    "domain": domain,
                    "snippet": snippet,
                    "url": href[:200],
                    "is_official": domain in _OFFICIAL,
                    "is_reputable": domain in _NEWS,
                })
            i += 7
        else:
            i += 1

    return results[:8]


def verify_claim(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.network_enabled:
        return {"query": query, "status": "not_found", "verified": False,
                "contradicted": False, "results": [], "summary": "Network disabled."}

    results = _search_ddg(query)

    official = [r for r in results if r["is_official"]]
    reputable = [r for r in results if r["is_reputable"] and not r["is_official"]]
    other = [r for r in results if not r["is_official"] and not r["is_reputable"]]

    verified = len(official) >= 1 or len(reputable) >= 2

    contradicted = False
    for r in official + reputable:
        if _DENIAL_RE.search(r.get("snippet", "")):
            contradicted = True
            break

    if not results:
        status = "not_found"
        summary = "No search results returned."
    elif contradicted:
        status = "contradicted"
        summary = "Official sources contradict this claim."
    elif verified:
        status = "verified"
        src = official[0]["domain"] if official else reputable[0]["domain"]
        summary = f"Confirmed by {src}."
    elif reputable:
        status = "unverified"
        summary = "Found on news sources but not officially confirmed."
    else:
        status = "unverified"
        summary = "Results found but no official confirmation."

    return {
        "query": query,
        "status": status,
        "verified": verified,
        "contradicted": contradicted,
        "total_results": len(results),
        "official_sources": len(official),
        "news_sources": len(reputable),
        "results": (official + reputable + other)[:6],
        "summary": summary,
    }


def verify_batch(queries: list[str]) -> list[dict[str, Any]]:
    return [verify_claim(q) for q in queries]
