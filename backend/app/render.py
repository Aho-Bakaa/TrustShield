"""Browser forensic evidence collection.

Playwright visits every link. Captures: redirect chain, DOM, all forms,
screenshot, network requests/responses, response security headers, TLS/SL
certificate info, console errors, JavaScript forensics (storage, timers,
cookies, navigator), WHOIS registration data, and DNS records.

Uses Playwright when available; otherwise degrades to a plain HTTP fetch + HTML
parse (no screenshot) so the pipeline never blocks on a missing browser.
"""
from __future__ import annotations

import base64
import socket
import ssl
from typing import Any
from urllib.parse import urlparse

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
        hidden = [{"name": i.get("name", ""), "value": (i.get("value", "") or "")[:80]}
                  for i in inputs if (i.get("type") or "text").lower() == "hidden"]
        forms.append({
            "action": (f.get("action") or "").strip(),
            "method": (f.get("method") or "GET").upper(),
            "num_inputs": len(inputs),
            "has_password": "password" in types,
            "captures_credentials": any(k in names for k in
                ["otp", "pin", "password", "card", "cvv", "upi", "account", "kyc"]) or "password" in types,
            "hidden_fields": hidden[:10],
        })

    page_dom = _reg_domain(final_url)
    external: set[str] = set()
    for tag, attr in (("a", "href"), ("script", "src"), ("img", "src"), ("form", "action"),
                       ("link", "href"), ("iframe", "src")):
        for el in soup.find_all(tag):
            val = el.get(attr) or ""
            if val.startswith("http"):
                d = _reg_domain(val)
                if d and d != page_dom:
                    external.add(d)

    text = " ".join(soup.get_text(" ").split())

    img_srcs: list[dict] = []
    for img in soup.find_all("img", src=True):
        src = str(img.get("src", ""))
        alt = str(img.get("alt", ""))[:40]
        if src.startswith("http"):
            img_srcs.append({"src": src[:200], "alt": alt, "cross_domain": _reg_domain(src) != page_dom})

    return {
        "title": title,
        "meta_description": _meta(soup, "og:description", "description"),
        "og_site_name": _meta(soup, "og:site_name"),
        "generator": _meta(soup, "generator"),
        "text_excerpt": text[:2000],
        "forms": forms,
        "has_login_form": any(f["has_password"] for f in forms),
        "captures_sensitive": any(f["captures_credentials"] for f in forms),
        "external_domains": sorted(external)[:15],
        "image_sources": img_srcs[:10],
        "grammar_issues": _scan_grammar(text),
        "final_url": final_url,
    }


def _scan_grammar(text: str) -> dict:
    import re
    typos = []
    patterns = [
        (r"\b(?:suspend|suspending)\s+(?:youre?|ur)\s+account\b", "Typical phishing grammar"),
        (r"\bkindly\b", "Nigerian/Indian phishing spelling"),
        (r"\b(?:dear|hello)\s+(?:sir|madam|customer|investor)\s*[,;]", "Generic greeting"),
        (r"\b(?:click|open|visit)\s+(?:on|the)\s+(?:this|below)\s+(?:link|url|website)\b", "Classic phishing CTA"),
    ]
    for pat, label in patterns:
        if re.search(pat, text, re.I):
            typos.append(label)
    return {"phishing_indicators": typos}


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


def _render_playwright(url: str, want_screenshot: bool) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    settings = get_settings()
    target = url if "://" in url else "http://" + url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        try:
            ctx = browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900},
                                      ignore_https_errors=True)
            page = ctx.new_page()

            network_requests: list[dict] = []
            network_responses: list[dict] = []

            def _on_request(req):
                network_requests.append({
                    "url": req.url[:200], "method": req.method,
                    "resource_type": req.resource_type,
                    "headers": {k: v for k, v in req.headers.items()
                                if k.lower() in ("content-type", "origin", "referer", "cookie", "authorization")},
                })

            def _on_response(resp):
                network_responses.append({
                    "url": resp.url[:200], "status": resp.status,
                    "headers": {k: v for k, v in resp.headers.items()
                                if k.lower() in ("content-type", "set-cookie", "server", "x-powered-by",
                                                 "content-security-policy", "strict-transport-security",
                                                 "x-content-type-options", "x-frame-options",
                                                 "referrer-policy", "permissions-policy", "access-control-allow-origin")},
                })

            page.on("request", _on_request)
            page.on("response", _on_response)

            console_messages: list[str] = []
            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"[:300]))

            failed_requests: list[str] = []
            page.on("requestfailed", lambda req: failed_requests.append(
                f"{req.method} {req.url[:150]} -> {req.failure or 'unknown'}"[:250]))

            dialog_messages: list[str] = []
            page.on("dialog", lambda d: (dialog_messages.append(f"[{d.type}] {d.message}"[:200]), d.dismiss()))

            popup_pages: list[str] = []
            page.on("popup", lambda p: (popup_pages.append(p.url[:200]), p.close()))

            resp = None
            nav_error = None
            try:
                resp = page.goto(target, wait_until="domcontentloaded", timeout=settings.render_timeout_ms)
            except Exception as exc:
                nav_error = str(exc)[:140]

            try:
                page.wait_for_load_state("networkidle", timeout=5000)
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
            forensic["console_messages"] = console_messages[-15:]
            forensic["console_error_count"] = sum(1 for m in console_messages if m.startswith("[error]"))
            forensic["console_warning_count"] = sum(1 for m in console_messages if m.startswith("[warning]"))
            forensic["failed_requests"] = failed_requests[:10]
            forensic["failed_request_count"] = len(failed_requests)
            forensic["network_requests"] = network_requests[:50]
            forensic["network_request_count"] = len(network_requests)
            forensic["network_responses"] = network_responses[:20]
            forensic["dialogues"] = dialog_messages[:5]
            forensic["popup_count"] = len(popup_pages)
            forensic["final_domain"] = _reg_domain(final_url)
            forensic["is_https"] = final_url.startswith("https://")

            forensic["security_headers"] = _extract_security_headers(network_responses, final_url)
            forensic["tls_info"] = _tls_lookup(final_url)
            forensic["js_forensics"] = _js_forensics(page)
            forensic["whois"] = _whois_lookup(_reg_domain(final_url))
            forensic["dns"] = _dns_lookup(_reg_domain(final_url))

            data.update(rendered=True, method="playwright",
                        status=(resp.status if resp else None),
                        redirect_chain=chain, cross_domain_redirect=_cross_domain(chain),
                        nav_error=nav_error, screenshot_b64=None,
                        forensic=forensic)

            if want_screenshot:
                try:
                    png = page.screenshot(full_page=True, type="png")
                    data["screenshot_b64"] = base64.b64encode(png).decode()
                except Exception as exc:
                    data["screenshot_error"] = str(exc)[:100]
            return data
        finally:
            browser.close()


def _extract_security_headers(network_responses: list[dict], final_url: str) -> dict:
    parsed = urlparse(final_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for r in network_responses:
        rurl = r.get("url", "")
        if rurl.startswith(base) or rurl == final_url:
            headers = r.get("headers", {})
            return {
                "csp": headers.get("content-security-policy", "")[:300],
                "hsts": headers.get("strict-transport-security", "")[:100],
                "x_content_type_options": headers.get("x-content-type-options", ""),
                "x_frame_options": headers.get("x-frame-options", ""),
                "referrer_policy": headers.get("referrer-policy", ""),
                "permissions_policy": headers.get("permissions-policy", "")[:200],
                "server": headers.get("server", "")[:80],
                "x_powered_by": headers.get("x-powered-by", "")[:80],
            }
    return {}


def _tls_lookup(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.scheme != "https":
        return {"available": False, "note": "Not HTTPS"}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert(binary_form=False)
                cipher = ssock.cipher()
                return {
                    "available": True,
                    "protocol": ssock.version() or "unknown",
                    "cipher": f"{cipher[0]} {cipher[1]} bits" if cipher else "unknown",
                    "issuer": dict((k, v) for k, v in cert.get("issuer", [])) if cert else {},
                    "subject": dict((k, v) for k, v in cert.get("subject", [])) if cert else {},
                    "not_before": cert.get("notBefore", "") if cert else "",
                    "not_after": cert.get("notAfter", "") if cert else "",
                    "san": cert.get("subjectAltName", [])[:5] if cert else [],
                }
    except Exception as exc:
        return {"available": False, "error": str(exc)[:200]}


def _whois_lookup(domain: str) -> dict:
    try:
        import whois
        w = whois.whois(domain)
        return {
            "registrar": str(w.registrar or "")[:100],
            "creation_date": str(w.creation_date or "")[:50],
            "expiration_date": str(w.expiration_date or "")[:50],
            "updated_date": str(w.updated_date or "")[:50],
            "name_servers": (w.name_servers or [])[:5],
        }
    except Exception:
        return {}


def _dns_lookup(domain: str) -> dict:
    result: dict = {}
    try:
        result["a_records"] = socket.gethostbyname_ex(domain)[2][:5]
    except Exception:
        result["a_records"] = []
    for rtype, label in [("MX", "mx_records"), ("TXT", "txt_records"), ("NS", "ns_records")]:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, rtype)
            result[label] = [str(a) for a in answers][:5]
        except Exception:
            result[label] = []
    return result


def _js_forensics(page) -> dict:
    forensics: dict = {}
    try:
        forensics = page.evaluate("""() => {
            const out = {};
            try {
                const scripts = document.querySelectorAll('script:not([src])');
                const inline = [];
                scripts.forEach(s => {
                    const txt = (s.textContent || '').slice(0, 100);
                    if (txt) inline.push(txt);
                });
                out.inline_script_count = inline.length;
            } catch(e) { out.inline_script_count = 0; }

            try {
                out.localStorage_keys = Object.keys(localStorage || {}).slice(0, 5);
                out.localStorage_item_count = localStorage ? localStorage.length : 0;
                out.sessionStorage_keys = Object.keys(sessionStorage || {}).slice(0, 5);
            } catch(e) { out.localStorage_keys = []; out.sessionStorage_keys = []; }

            try {
                out.cookie_string = document.cookie.slice(0, 300);
                out.cookie_count = document.cookie ? document.cookie.split(';').length : 0;
            } catch(e) { out.cookie_string = ''; out.cookie_count = 0; }

            try {
                out.navigator = {
                    language: navigator.language,
                    platform: navigator.platform,
                    cookieEnabled: navigator.cookieEnabled,
                    onLine: navigator.onLine,
                };
            } catch(e) { out.navigator = {}; }

            try {
                const timers = [];
                const origSetTimeout = window.setTimeout;
                window.setTimeout = function(fn, delay) {
                    timers.push({delay: delay, type: 'setTimeout'});
                    return origSetTimeout.call(this, fn, delay);
                };
                const origSetInterval = window.setInterval;
                window.setInterval = function(fn, delay) {
                    timers.push({delay: delay, type: 'setInterval'});
                    return origSetInterval.call(this, fn, delay);
                };
                setTimeout(function() { out.timers_detected = timers.slice(0, 5); }, 2000);
            } catch(e) { out.timers_detected = []; }

            try {
                const hiddenInputs = document.querySelectorAll('input[type=hidden]');
                const hidden = [];
                hiddenInputs.forEach(i => {
                    hidden.push({name: i.name || '', value: (i.value || '').slice(0, 100)});
                });
                out.hidden_inputs = hidden.slice(0, 10);
            } catch(e) { out.hidden_inputs = []; }

            try {
                out.location_info = {
                    href: window.location.href,
                    hostname: window.location.hostname,
                    pathname: window.location.pathname,
                    protocol: window.location.protocol,
                };
            } catch(e) {}

            try {
                out.meta_tags = [];
                document.querySelectorAll('meta').forEach(m => {
                    const name = m.getAttribute('name') || m.getAttribute('property') || '';
                    const content = (m.getAttribute('content') || '').slice(0, 100);
                    if (name && content) out.meta_tags.push({name, content});
                });
            } catch(e) { out.meta_tags = []; }

            return out;
        }""")
    except Exception:
        pass
    return forensics


def _collect_forensics(page, html: str, final_url: str) -> dict[str, Any]:
    forensic: dict[str, Any] = {}

    try:
        resource_info = page.evaluate("""() => {
            try {
                const entries = performance.getEntriesByType('resource');
                const failed = entries.filter(e => {
                    return e.transferSize === 0 && e.decodedBodySize === 0 && e.duration > 0;
                });
                return { total_resources: entries.length, failed_count: failed.length };
            } catch(e) { return { total_resources: 0, failed_count: 0 }; }
        }""")
        forensic["resource_count"] = resource_info.get("total_resources", 0)
        forensic["failed_resource_count"] = resource_info.get("failed_count", 0)
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
                    sources.push(src.slice(0, 150));
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
                const text = (a.textContent || '').trim().slice(0, 100);
                const key = href + '|' + text;
                if (seen.has(key)) return;
                seen.add(key);
                links.push({ href: href.slice(0, 250), text });
                if (links.length >= 40) return;
            });
            return links;
        }""")
        forensic["all_links"] = links_data[:40]
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
                h1_count: document.querySelectorAll('h1').length,
                h2_count: document.querySelectorAll('h2').length,
            };
        }""")
        forensic.update(dom_metrics)
    except Exception:
        pass

    soup = BeautifulSoup(html or "", "html.parser")
    meta_refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    forensic["meta_refresh_tag"] = meta_refresh.get("content", "")[:200] if meta_refresh else None

    page_dom = _reg_domain(final_url)
    cross_domain_links = []
    for link in forensic.get("all_links", []):
        href = link.get("href", "")
        link_dom = _reg_domain(href) if href.startswith("http") else ""
        if link_dom and link_dom != page_dom:
            cross_domain_links.append({"href": href[:200], "text": link.get("text", "")[:80], "cross_domain": True})
    forensic["cross_domain_links"] = cross_domain_links[:15]
    forensic["cross_domain_link_count"] = len(cross_domain_links)

    return forensic


def render(url: str, want_screenshot: bool | None = None) -> dict[str, Any]:
    settings = get_settings()
    if want_screenshot is None:
        want_screenshot = settings.render_screenshots
    if not settings.network_enabled:
        _log.info("render skipped (network disabled) url=%s", url[:80])
        return {"rendered": False, "method": "disabled", "redirect_chain": [], "screenshot_b64": None}
    if settings.render_enabled:
        try:
            data = _render_playwright(url, want_screenshot)
            _log.info("render %s via playwright ok=%s status=%s shot=%s title=%r",
                      url[:70], data.get("rendered"), data.get("status"),
                      bool(data.get("screenshot_b64")), (data.get("title") or "")[:50])
            return data
        except Exception as exc:
            _log.warning("playwright failed (%s) -> HTTP fallback for %s", str(exc)[:80], url[:70])
    data = _fetch_http(url)
    _log.info("render %s via http_fetch ok=%s status=%s",
              url[:70], data.get("rendered"), data.get("status"))
    return data
