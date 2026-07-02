"""Browser-based evidence collection.

Renders a suspicious URL and returns rich, structured evidence:
  - final URL after redirects + the full redirect chain (+ cross-domain flag)
  - page title and metadata (og:site_name, description, generator)
  - forms (esp. credential / payment capture)
  - external resource domains
  - a SCREENSHOT (base64 PNG) for downstream vision analysis
  - visible-text excerpt

Uses Playwright when available; otherwise degrades to a plain HTTP fetch + HTML
parse (no screenshot) so the pipeline never blocks on a missing browser.
"""
from __future__ import annotations

import base64
from typing import Any

import tldextract
from bs4 import BeautifulSoup

from .config import get_settings
from .log import get_logger

_log = get_logger("render")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _reg_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return ".".join(x for x in [ext.domain, ext.suffix] if x).lower()


def _meta(soup: BeautifulSoup, *keys: str) -> str:
    for k in keys:
        tag = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _analyze_html(html: str, final_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    forms: list[dict[str, Any]] = []
    for f in soup.find_all("form"):
        inputs = f.find_all("input")
        types = [(i.get("type") or "text").lower() for i in inputs]
        names = " ".join((i.get("name") or "") + " " + (i.get("placeholder") or "") for i in inputs).lower()
        forms.append({
            "action": (f.get("action") or "").strip(),
            "num_inputs": len(inputs),
            "has_password": "password" in types,
            "captures_credentials": any(k in names for k in
                ["otp", "pin", "password", "card", "cvv", "upi", "account", "kyc"]) or "password" in types,
        })

    page_dom = _reg_domain(final_url)
    external: set[str] = set()
    for tag, attr in (("a", "href"), ("script", "src"), ("img", "src"), ("form", "action")):
        for el in soup.find_all(tag):
            val = el.get(attr) or ""
            if val.startswith("http"):
                d = _reg_domain(val)
                if d and d != page_dom:
                    external.add(d)

    text = " ".join(soup.get_text(" ").split())
    return {
        "title": title,
        "meta_description": _meta(soup, "og:description", "description"),
        "og_site_name": _meta(soup, "og:site_name"),
        "generator": _meta(soup, "generator"),
        "text_excerpt": text[:1600],
        "forms": forms,
        "has_login_form": any(f["has_password"] for f in forms),
        "captures_sensitive": any(f["captures_credentials"] for f in forms),
        "external_domains": sorted(external)[:12],
        "final_url": final_url,
    }


def _cross_domain(chain: list[str]) -> bool:
    domains = {_reg_domain(u) for u in chain if _reg_domain(u)}
    return len(domains) > 1


def _fetch_http(url: str) -> dict[str, Any]:
    import httpx

    settings = get_settings()
    target = url if "://" in url else "http://" + url
    chain: list[str] = []
    try:
        with httpx.Client(follow_redirects=True, timeout=settings.fetch_timeout_seconds,
                          headers={"User-Agent": _UA}) as client:
            resp = client.get(target)
            chain = [str(h.url) for h in resp.history] + [str(resp.url)]
            data = _analyze_html(resp.text, str(resp.url))
            data.update(rendered=True, method="http_fetch", status=resp.status_code,
                        redirect_chain=chain, cross_domain_redirect=_cross_domain(chain),
                        screenshot_b64=None)
            return data
    except Exception as exc:
        return {"rendered": False, "method": "http_fetch", "error": str(exc)[:200],
                "redirect_chain": chain, "screenshot_b64": None}


def _security_headers(page) -> dict[str, str | None]:
    """Extract security-relevant response headers via Playwright's evaluate."""
    headers: dict[str, str | None] = {}
    try:
        entries = page.evaluate("""() => {
            const nav = performance.getEntriesByType('navigation');
            if (!nav || nav.length === 0) return [];
            try {
                return [nav[0].serverTiming || []];
            } catch(e) { return []; }
        }""")
    except Exception:
        entries = []
    try:
        raw = page.evaluate("""() => {
            const out = {};
            try {
                const meta = document.querySelector('meta[http-equiv]');
                if (meta) out['meta_refresh'] = meta.getAttribute('content') || '';
            } catch(e) {}
            return out;
        }""")
    except Exception:
        raw = {}

    try:
        sec_info = page.evaluate("""() => {
            return {
                protocol: window.location.protocol,
                hostname: window.location.hostname,
                href: window.location.href,
                referrer: document.referrer || '',
                cookie_count: document.cookie ? document.cookie.split(';').length : 0,
                has_js_cookies: document.cookie.length > 0,
            };
        }""")
    except Exception:
        sec_info = {}

    return {
        "protocol": sec_info.get("protocol", ""),
        "referrer": sec_info.get("referrer", ""),
        "cookie_count": sec_info.get("cookie_count", 0),
        "meta_refresh": raw.get("meta_refresh"),
    }


def _collect_forensics(page, html: str, final_url: str) -> dict[str, Any]:
    """Gather rich forensic evidence from the rendered page via Playwright."""
    forensic: dict[str, Any] = {}

    sec = _security_headers(page)
    forensic["protocol"] = sec.get("protocol", "")
    forensic["referrer"] = sec.get("referrer", "")
    forensic["cookie_count"] = sec.get("cookie_count", 0)

    try:
        console_msgs = page.evaluate("""() => {
            const msgs = [];
            try {
                const entries = performance.getEntriesByType('resource');
                const failed = entries.filter(e => {
                    return e.transferSize === 0 && e.decodedBodySize === 0 && e.duration > 0;
                });
                return { total_resources: entries.length, failed_count: failed.length };
            } catch(e) { return { total_resources: 0, failed_count: 0 }; }
        }""")
        forensic["resource_count"] = console_msgs.get("total_resources", 0)
        forensic["failed_resource_count"] = console_msgs.get("failed_count", 0)
    except Exception:
        forensic["resource_count"] = 0
        forensic["failed_resource_count"] = 0

    try:
        iframe_info = page.evaluate("""() => {
            const iframes = document.querySelectorAll('iframe');
            const sources = [];
            iframes.forEach(f => {
                const src = f.getAttribute('src') || '';
                if (src && !src.startsWith('about:') && !src.startsWith('blob:')) {
                    sources.push(src);
                }
            });
            return { iframe_count: iframes.length, iframe_srcs: sources.slice(0, 10) };
        }""")
        forensic["iframe_count"] = iframe_info.get("iframe_count", 0)
        forensic["iframe_sources"] = iframe_info.get("iframe_srcs", [])
    except Exception:
        forensic["iframe_count"] = 0
        forensic["iframe_sources"] = []

    try:
        links_data = page.evaluate("""() => {
            const anchors = document.querySelectorAll('a[href]');
            const links = [];
            const seen = new Set();
            anchors.forEach(a => {
                const href = a.href || '';
                if (!href || href.startsWith('javascript:') || href.startsWith('#') || href.startsWith('mailto:')) return;
                const text = (a.textContent || '').trim().slice(0, 80);
                const key = href + '|' + text;
                if (seen.has(key)) return;
                seen.add(key);
                links.push({ href, text });
                if (links.length >= 30) return;
            });
            return links;
        }""")
        forensic["all_links"] = links_data[:30]
        forensic["total_link_count"] = len(links_data)
    except Exception:
        forensic["all_links"] = []
        forensic["total_link_count"] = 0

    try:
        dom_metrics = page.evaluate("""() => {
            return {
                script_count: document.querySelectorAll('script').length,
                style_count: document.querySelectorAll('link[rel=stylesheet], style').length,
                form_count: document.querySelectorAll('form').length,
                input_count: document.querySelectorAll('input').length,
                image_count: document.querySelectorAll('img').length,
                body_text_length: (document.body ? document.body.innerText.length : 0),
            };
        }""")
        forensic.update(dom_metrics)
    except Exception:
        pass

    soup = BeautifulSoup(html or "", "html.parser")
    meta_refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    if meta_refresh:
        forensic["meta_refresh_tag"] = meta_refresh.get("content", "")[:200]
    else:
        forensic["meta_refresh_tag"] = None

    suspicious_links = []
    page_dom = _reg_domain(final_url)
    for link in forensic.get("all_links", []):
        href = link.get("href", "")
        link_dom = _reg_domain(href) if href.startswith("http") else ""
        if link_dom and link_dom != page_dom:
            text = link.get("text", "")
            suspicious_links.append({"href": href, "text": text, "cross_domain": True})
    forensic["cross_domain_links"] = suspicious_links[:15]
    forensic["cross_domain_link_count"] = len(suspicious_links)

    return forensic


def _render_playwright(url: str, want_screenshot: bool) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    settings = get_settings()
    target = url if "://" in url else "http://" + url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        try:
            ctx = browser.new_context(user_agent=_UA, viewport={"width": 1024, "height": 800},
                                      ignore_https_errors=True)
            page = ctx.new_page()

            console_messages: list[str] = []
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"[:200]))

            failed_requests: list[str] = []
            page.on("requestfailed", lambda req: failed_requests.append(
                f"{req.method} {req.url[:120]} — {req.failure}"[:200]))

            resp = None
            nav_error = None
            try:
                resp = page.goto(target, wait_until="domcontentloaded", timeout=settings.render_timeout_ms)
            except Exception as exc:
                nav_error = str(exc)[:140]
            try:
                page.wait_for_load_state("networkidle", timeout=3500)
            except Exception:
                pass

            html = ""
            try:
                html = page.content()
            except Exception:
                pass
            final_url = page.url
            data = _analyze_html(html, final_url)

            chain: list[str] = []
            if resp is not None:
                req = resp.request
                hops: list[str] = []
                while req is not None:
                    hops.append(req.url)
                    req = req.redirected_from
                chain = list(reversed(hops))
            if final_url and final_url not in chain:
                chain.append(final_url)
            if not chain:
                chain = [target]

            forensic = _collect_forensics(page, html, final_url)
            forensic["console_messages"] = console_messages[-10:]  # last 10
            forensic["console_error_count"] = sum(1 for m in console_messages if m.startswith("[error]"))
            forensic["failed_requests"] = failed_requests[:10]
            forensic["failed_request_count"] = len(failed_requests)
            forensic["final_domain"] = _reg_domain(final_url)
            forensic["is_https"] = final_url.startswith("https://")

            data.update(rendered=True, method="playwright",
                        status=(resp.status if resp else None),
                        redirect_chain=chain, cross_domain_redirect=_cross_domain(chain),
                        nav_error=nav_error, screenshot_b64=None,
                        forensic=forensic)

            if want_screenshot:
                try:
                    png = page.screenshot(full_page=False, type="png")
                    data["screenshot_b64"] = base64.b64encode(png).decode()
                except Exception as exc:
                    data["screenshot_error"] = str(exc)[:100]
            return data
        finally:
            browser.close()


def render(url: str, want_screenshot: bool | None = None) -> dict[str, Any]:
    """Best-effort page evidence. Never raises."""
    settings = get_settings()
    if want_screenshot is None:
        want_screenshot = settings.render_screenshots
    if not settings.network_enabled:
        _log.info("render skipped (network disabled) url=%s", url[:80])
        return {"rendered": False, "method": "disabled", "redirect_chain": [], "screenshot_b64": None}
    if settings.render_enabled:
        try:
            data = _render_playwright(url, want_screenshot)
            _log.info("render %s via playwright ok=%s status=%s captures=%s shot=%s title=%r",
                      url[:70], data.get("rendered"), data.get("status"), data.get("captures_sensitive"),
                      bool(data.get("screenshot_b64")), (data.get("title") or "")[:50])
            return data
        except Exception as exc:
            _log.warning("playwright failed (%s) -> HTTP fallback for %s", str(exc)[:80], url[:70])
    data = _fetch_http(url)
    _log.info("render %s via http_fetch ok=%s status=%s captures=%s",
              url[:70], data.get("rendered"), data.get("status"), data.get("captures_sensitive"))
    return data
