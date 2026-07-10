"""LLM-callable web search tool.

The verdict LLM can invoke search to verify factual claims, check if
a website/news/article is legitimate, or cross-reference information
against official regulatory sources and reputable financial news.

Returns structured results the LLM can directly incorporate into its
final verdict. Uses DuckDuckGo HTML search (no API key required).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .config import get_settings
from .log import get_logger

_log = get_logger("search")

_TIMEOUT = 6.0
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

_OFFICIAL = {"sebi.gov.in", "rbi.org.in", "nseindia.com", "bseindia.com", "scores.sebi.gov.in", "nsdl.co.in", "cdslindia.com", "amfiindia.com"}
_NEWS = {"moneycontrol.com", "economictimes.indiatimes.com", "livemint.com", "bloombergquint.com", "businesstoday.in", "thehindubusinessline.com", "cnbctv18.com", "ndtvprofit.com"}


def verify_claim(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.network_enabled:
        return {"query": query, "verified": False, "results": [], "summary": "Network disabled. Cannot verify."}

    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query[:100])}"
        with httpx.Client(headers={"User-Agent": _UA}, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return {"query": query, "verified": False, "results": [], "summary": "Search unavailable."}

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for r in soup.select(".result")[:8]:
                a = r.select_one(".result__a")
                s = r.select_one(".result__snippet")
                if a and a.get("href"):
                    from urllib.parse import urlparse
                    host = (urlparse(a["href"]).hostname or "").lower().lstrip("www.")
                    results.append({
                        "title": a.get_text(strip=True)[:120],
                        "domain": host,
                        "snippet": s.get_text(strip=True)[:200] if s else "",
                        "is_official": host in _OFFICIAL,
                        "is_reputable": host in _NEWS,
                    })

            official = [r for r in results if r["is_official"]]
            reputable = [r for r in results if r["is_reputable"] and not r["is_official"]]
            other = [r for r in results if not r["is_official"] and not r["is_reputable"]]

            verified = len(official) >= 1 or len(reputable) >= 2
            contradicted = len(results) == 0

            summary_parts = []
            if official:
                summary_parts.append(f"Found on {len(official)} official sources ({', '.join(r['domain'] for r in official[:2])})")
            if reputable:
                summary_parts.append(f"Found on {len(reputable)} news sources ({', '.join(r['domain'] for r in reputable[:2])})")
            if not summary_parts:
                summary_parts.append("No matching information found on any official or reputable source")

            return {
                "query": query,
                "verified": verified,
                "contradicted": contradicted,
                "total_results": len(results),
                "official_sources": len(official),
                "news_sources": len(reputable),
                "results": (official + reputable + other)[:6],
                "summary": ". ".join(summary_parts),
            }
    except Exception as exc:
        _log.debug("search failed: %s", str(exc)[:80])
        return {"query": query, "verified": False, "results": [], "summary": f"Search error: {str(exc)[:80]}"}


def verify_batch(queries: list[str]) -> list[dict[str, Any]]:
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(verify_claim, q): q for q in queries}
        for f in futures:
            try:
                results.append(f.result(timeout=_TIMEOUT + 2))
            except Exception:
                results.append({"query": futures[f], "verified": False, "results": [], "summary": "Search timed out"})
    return results
