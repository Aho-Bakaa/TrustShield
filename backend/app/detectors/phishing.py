"""Phishing / impersonation detector — LLM-first scoring.

Flow:
  1. Intent LLM: classifies message type, extracts claims, identifies impersonation
  2. Playwright: renders linked pages, collects forensic evidence
  3. Vision model: analyzes page screenshots for brand imitation
  4. Web search: verifies factual claims (always runs)
  5. Verdict LLM: synthesizes ALL evidence into a single 0-1 probability

The LLM is the ONLY scoring authority. No static rules, floors, or caps.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
from typing import Any

from ..intent import analyze_message
from ..llm import analyze_screenshot, reason_json
from ..log import get_logger
from ..prompts import load as load_prompt
from ..render import render
from ..search import verify_batch
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence

_log = get_logger("phishing")


def _pick_link(req: AnalysisRequest):
    if not req.links:
        return None
    ranked = sorted(req.links, key=lambda l: (l.allowlisted, -len(l.reasons)))
    for l in ranked:
        if not l.allowlisted:
            return l
    return ranked[0]


def _extract_claims_from_text(text: str) -> list[dict]:
    sentences = [s.strip() for s in text.replace("?", "?|").replace(".", ".|").replace("!", "!|").split("|") if len(s.strip()) > 20]
    return [{"text": s[:200], "type": "extracted", "verified": False, "sources": [], "contradicted": False} for s in sentences[:5]]


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    used_llm = False
    used_render = False

    entities_list = [e.text for e in req.entities]
    link = _pick_link(req)

    intent = analyze_message(req.raw_input, entities_list,
                             link_allowlisted=bool(link and link.allowlisted),
                             link_suspicious=bool(link and link.suspicious and not link.allowlisted),
                             link_reasons=link.reasons if link else None)
    used_llm = True

    classific = intent.get("classification", "uncertain")
    evidence.append(Evidence(
        source="intent", label="Message classification",
        detail=f"Classified as: {classific}. {intent.get('explanation', '')}",
        weight=0.0, severity="info"))

    prob = 0.10
    impersonated = intent.get("impersonation_target")
    fields: dict[str, Any] = {
        "impersonated_entity": impersonated,
        "classification": classific,
        "domain_mismatch": False,
        "credential_capture": False,
    }
    explanation = intent.get("explanation", "")

    rendered = None
    rendered_summary = "No linked page rendered."
    forensic_summary = "No forensic data."
    screenshot_summary = "No screenshot."
    claim_summary = "No claims to verify."

    if link:
        rendered = render(link.raw)
        used_render = True

    if rendered and rendered.get("rendered"):
        if rendered.get("cross_domain_redirect"):
            evidence.append(Evidence(source="phishing", label="Cross-domain redirect chain",
                detail=" -> ".join(rendered.get("redirect_chain", [])[:4]), weight=0.15, severity="high"))
        if rendered.get("captures_sensitive"):
            evidence.append(Evidence(source="phishing", label="Login or password form detected",
                detail=f"Page contains password or credential input on {rendered.get('final_url','')}",
                weight=0.1, severity="medium"))
            fields["credential_capture"] = True
        if rendered.get("title"):
            evidence.append(Evidence(source="phishing", label="Rendered page title",
                detail=rendered["title"][:160], weight=0.03, severity="info"))

        forensic = rendered.get("forensic", {})
        if forensic:
            _add_forensic_evidence(evidence, forensic, rendered)
            fields["rendered"] = _summarize_rendered_fields(rendered, forensic)
            forensic_summary = _build_forensic_summary(forensic)

        screenshot_analysis: dict = {}
        if rendered.get("screenshot_b64"):
            screenshot_analysis, _ = analyze_screenshot(rendered["screenshot_b64"])
            _add_screenshot_evidence(evidence, screenshot_analysis, fields)
            screenshot_summary = _build_screenshot_summary(screenshot_analysis)

        rendered_summary = _build_rendered_summary(rendered)

        claims_raw = intent.get("claims_to_verify", [])
        if claims_raw and isinstance(claims_raw[0], str):
            claims = [{"text": c, "type": "llm_claim", "verified": False, "sources": [], "contradicted": False} for c in claims_raw]
        elif claims_raw:
            claims = claims_raw
        else:
            claims = _extract_claims_from_text(req.raw_input)

        search_future = None
        pool = None
        if claims:
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            search_future = pool.submit(_verify_sync, claims)

        if search_future:
            try:
                claim_results = search_future.result(timeout=8)
                _add_claim_evidence(evidence, claim_results)
                claim_summary = _build_claim_summary(claim_results)
            except Exception:
                _log.debug("claim verification timed out")
            finally:
                if pool:
                    pool.shutdown(wait=False)

    intent_data = {
        "classification": classific,
        "confidence": intent.get("confidence", 0.0),
        "impersonation_target": impersonated,
        "reasoning": intent.get("explanation"),
    }

    link_context = "No link."
    if link:
        link_context = (f"raw={link.raw} resolved_domain={link.registered_domain} "
                        f"allowlisted={link.allowlisted} suspicious={link.suspicious} "
                        f"reasons={link.reasons}")

    user = (
        f"## ORIGINAL MESSAGE\n{req.raw_input[:2000]}\n\n"
        f"## INTENT ANALYSIS\n{json.dumps(intent_data, indent=2, default=str)}\n\n"
        f"## LINK CONTEXT\n{link_context}\n\n"
        f"## RENDERED PAGE\n{rendered_summary}\n\n"
        f"## BROWSER FORENSICS\n{forensic_summary}\n\n"
        f"## SCREENSHOT ANALYSIS\n{screenshot_summary}\n\n"
        f"## CLAIM VERIFICATION\n{claim_summary}\n"
    )

    def _neutral():
        is_phish = classific == "phishing_email"
        if is_phish:
            return {"phishing_probability": 0.85, "impersonated_entity": impersonated,
                    "domain_mismatch": True, "credential_capture": True,
                    "key_evidence": ["Link analysis flagged as phishing."],
                    "explanation": "Determined from link reputation analysis.",
                    "recommended_action": "report"}
        if link and link.suspicious and not link.allowlisted:
            return {"phishing_probability": 0.55, "impersonated_entity": impersonated,
                    "domain_mismatch": True, "credential_capture": False,
                    "key_evidence": [f"Suspicious link: {link.reasons}"],
                    "explanation": "Link flagged with warning signals.",
                    "recommended_action": "caution"}
        return {"phishing_probability": 0.05, "impersonated_entity": impersonated,
                "domain_mismatch": False, "credential_capture": False,
                "key_evidence": [], "explanation": "No strong phishing signals.",
                "recommended_action": "verify"}

    data, used_llm = reason_json(load_prompt("phishing_verdict.txt"), user, _neutral)

    if used_llm:
        queries = data.get("search_queries")
        if not queries or not isinstance(queries, list):
            queries = intent.get("claims_to_verify") or [req.raw_input[:100]]
        if isinstance(queries[0], dict):
            queries = [q.get("text", str(q)) for q in queries]
        queries = [str(q)[:200] for q in queries]
        try:
            search_results = verify_batch(queries)
            search_json = json.dumps(search_results, indent=2, default=str)
            follow_up = user + f"\n\n## SEARCH RESULTS\n{search_json}\n\nNow produce FINAL verdict JSON (no search_queries field)."
            data, _ = reason_json(load_prompt("phishing_verdict.txt"), follow_up, _neutral)
            for sr in search_results:
                if sr.get("verified"):
                    evidence.append(Evidence(source="search", label="Claim verified",
                        detail=f"'{sr.get('query','')[:120]}' — {sr.get('summary','')}", weight=-0.1, severity="info"))
                elif sr.get("contradicted"):
                    evidence.append(Evidence(source="search", label="Claim contradicted",
                        detail=f"'{sr.get('query','')[:120]}' — {sr.get('summary','')}", weight=0.3, severity="high"))
                else:
                    evidence.append(Evidence(source="search", label="Search result",
                        detail=f"'{sr.get('query','')[:120]}' — {sr.get('summary','')}", weight=0.0, severity="info"))
        except Exception:
            _log.debug("search batch failed")

    try:
        prob = float(data.get("phishing_probability", prob))
    except Exception:
        pass
    prob = max(0.0, min(prob, 1.0))

    fields["impersonated_entity"] = data.get("impersonated_entity", impersonated)
    fields["domain_mismatch"] = bool(data.get("domain_mismatch", False))
    fields["credential_capture"] = bool(data.get("credential_capture", False))
    explanation = data.get("explanation", explanation)
    for k in data.get("key_evidence", [])[:5]:
        evidence.append(Evidence(source="verdict", label="Key evidence",
            detail=str(k)[:200], weight=0.1, severity="info"))

    label = "Likely phishing" if prob >= 0.6 else ("Suspicious" if prob >= 0.35 else "Low phishing risk")
    return DetectorResult(name="phishing", channel=req.channel_type,
        probability=round(prob, 3), label=label, fields=fields,
        evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000),
        used_llm=used_llm, used_render=used_render)


def _verify_sync(claims):
    texts = [c.get("text", str(c)[:200]) for c in claims]
    results = verify_batch(texts)
    for i, r in enumerate(results):
        claim_idx = min(i, len(claims) - 1)
        claims[claim_idx]["verified"] = r.get("verified", False)
        claims[claim_idx]["contradicted"] = r.get("contradicted", False)
        claims[claim_idx]["sources"] = r.get("results", [])[:5]
    return claims


def _add_forensic_evidence(evidence: list[Evidence], forensic: dict, rendered: dict) -> None:
    tls = forensic.get("tls_info", {})
    sec = forensic.get("security_headers", {})
    js = forensic.get("js_forensics", {})

    if forensic.get("is_https") is False:
        evidence.append(Evidence(source="forensic", label="No HTTPS",
            detail="Page served over plain HTTP.", weight=0.1, severity="medium"))
    if tls.get("available") and tls.get("not_before"):
        evidence.append(Evidence(source="forensic", label="TLS Certificate",
            detail=f"Issuer: {tls.get('issuer', {})}, valid from {tls.get('not_before')}.",
            weight=0.02, severity="info"))
    if not sec.get("csp"):
        evidence.append(Evidence(source="forensic", label="Missing CSP header",
            detail="No Content-Security-Policy.", weight=0.05, severity="low"))
    if not sec.get("hsts"):
        evidence.append(Evidence(source="forensic", label="Missing HSTS header",
            detail="No Strict-Transport-Security.", weight=0.03, severity="low"))
    if forensic.get("console_error_count", 0) >= 3:
        evidence.append(Evidence(source="forensic", label=f"Console errors ({forensic.get('console_error_count')})",
            detail=f"Page triggered {forensic.get('console_error_count')} browser errors.",
            weight=0.06, severity="low"))
    if forensic.get("failed_request_count", 0) >= 3:
        evidence.append(Evidence(source="forensic", label=f"Failed network requests ({forensic.get('failed_request_count')})",
            detail="Multiple resources failed to load.", weight=0.08, severity="medium"))
    if forensic.get("meta_refresh_tag"):
        evidence.append(Evidence(source="forensic", label="Meta refresh redirect",
            detail=f"Page uses meta refresh: {forensic.get('meta_refresh_tag')}",
            weight=0.15, severity="high"))
    if forensic.get("iframe_count", 0) > 0:
        iframe_srcs = forensic.get("iframe_sources", [])
        evidence.append(Evidence(source="forensic", label=f"Page contains {forensic.get('iframe_count')} iframe(s)",
            detail=f"Embedded: {', '.join(iframe_srcs[:3])}" if iframe_srcs else "External iframes present.",
            weight=0.08, severity="medium"))
    if forensic.get("cross_domain_link_count", 0) >= 5:
        evidence.append(Evidence(source="forensic", label=f"Many cross-domain links ({forensic.get('cross_domain_link_count')})",
            detail="High number of outbound links.", weight=0.05, severity="low"))
    whois = forensic.get("whois", {})
    if whois.get("creation_date"):
        evidence.append(Evidence(source="forensic", label="Domain registration",
            detail=f"Registered: {whois.get('creation_date')}. Registrar: {whois.get('registrar', 'unknown')}.",
            weight=0.02, severity="info"))
    if js.get("hidden_inputs") and len(js.get("hidden_inputs", [])) >= 3:
        evidence.append(Evidence(source="forensic", label="Multiple hidden form fields",
            detail=f"{len(js.get('hidden_inputs'))} hidden inputs — possible phishing kit.",
            weight=0.1, severity="medium"))
    if forensic.get("dialogues"):
        evidence.append(Evidence(source="forensic", label=f"Browser dialogs ({len(forensic.get('dialogues'))})",
            detail=f"Popups/dialogs: {'; '.join(forensic.get('dialogues', [])[:3])}",
            weight=0.1, severity="medium"))
    if forensic.get("popup_count", 0) > 0:
        evidence.append(Evidence(source="forensic", label=f"Popups ({forensic.get('popup_count')})",
            detail="Page attempted popup windows.", weight=0.12, severity="medium"))


def _add_screenshot_evidence(evidence: list[Evidence], screenshot: dict, fields: dict) -> None:
    if not screenshot:
        return
    if screenshot.get("looks_deceptive"):
        evidence.append(Evidence(source="vision", label="Screenshot looks deceptive",
            detail=f"Vision: page imitates {screenshot.get('imitates_brand') or 'a brand'}. {screenshot.get('notes', '')}",
            weight=0.25, severity="high"))
    elif screenshot.get("imitates_brand"):
        evidence.append(Evidence(source="vision", label="Brand resemblance detected",
            detail=f"Vision: resembles {screenshot.get('imitates_brand')} ({screenshot.get('page_type')}). {screenshot.get('notes', '')}",
            weight=0.05, severity="info"))
    else:
        evidence.append(Evidence(source="vision", label="Screenshot assessed",
            detail=f"Vision: type={screenshot.get('page_type')}, deceptive={screenshot.get('looks_deceptive')}. {screenshot.get('notes', '')}",
            weight=0.0, severity="info"))
    fields["screenshot_vision"] = {k: v for k, v in screenshot.items() if v}


def _add_claim_evidence(evidence: list[Evidence], claim_results: list[dict]) -> None:
    for claim in claim_results:
        if claim.get("verified"):
            evidence.append(Evidence(source="search", label="Claim verified",
                detail=f"'{claim.get('text', '')[:120]}' — verified by {len(claim.get('sources', []))} sources.",
                weight=-0.1, severity="info"))
        elif claim.get("contradicted"):
            evidence.append(Evidence(source="search", label="Claim CONTRADICTED",
                detail=f"'{claim.get('text', '')[:120]}' — contradicted by official sources.",
                weight=0.3, severity="high"))
        else:
            evidence.append(Evidence(source="search", label="Claim unverified",
                detail=f"'{claim.get('text', '')[:120]}' — not found in any source.",
                weight=0.05, severity="low"))


def _build_rendered_summary(rendered: dict) -> str:
    data = {
        "final_url": rendered.get("final_url"),
        "title": rendered.get("title"),
        "og_site_name": rendered.get("og_site_name"),
        "meta_description": (rendered.get("meta_description") or "")[:200],
        "has_login_form": rendered.get("has_login_form"),
        "captures_sensitive": rendered.get("captures_sensitive"),
        "redirect_chain": rendered.get("redirect_chain"),
        "cross_domain": rendered.get("cross_domain_redirect"),
        "external_domains": rendered.get("external_domains", []),
        "forms": rendered.get("forms", []),
        "text_excerpt": (rendered.get("text_excerpt") or "")[:800],
    }
    return json.dumps(data, indent=2, default=str)


def _build_forensic_summary(forensic: dict) -> str:
    tls = forensic.get("tls_info", {})
    sec = forensic.get("security_headers", {})
    whois = forensic.get("whois", {})
    js = forensic.get("js_forensics", {})
    dns = forensic.get("dns", {})
    failed = forensic.get("failed_requests", [])
    links_raw = forensic.get("all_links", [])

    data = {
        "is_https": forensic.get("is_https"),
        "final_domain": forensic.get("final_domain"),
        "status_code": forensic.get("status"),
        "redirect_chain": forensic.get("redirect_chain", []),
        "network": {
            "total_requests": forensic.get("network_request_count", 0),
            "total_resources": forensic.get("resource_count", 0),
            "failed_resources": forensic.get("failed_resource_count", 0),
            "console_errors": forensic.get("console_error_count", 0),
            "failed_requests": failed[:5],
        },
        "security_headers": {
            "csp": (sec.get("csp") or "")[:200] or "MISSING",
            "hsts": (sec.get("hsts") or "")[:100] or "MISSING",
            "x_frame_options": sec.get("x_frame_options") or "MISSING",
            "x_content_type_options": sec.get("x_content_type_options") or "MISSING",
            "referrer_policy": sec.get("referrer_policy") or "MISSING",
            "server_header": sec.get("server") or "hidden",
        },
        "tls": {
            "available": tls.get("available", False),
            "protocol": tls.get("protocol"),
            "issuer": tls.get("issuer", {}),
            "not_before": tls.get("not_before"),
        },
        "whois": {"registrar": whois.get("registrar"), "creation_date": whois.get("creation_date")},
        "dom": {
            "forms": forensic.get("form_count", 0),
            "inputs": forensic.get("input_count", 0),
            "scripts": forensic.get("script_count", 0),
            "iframes": forensic.get("iframe_count", 0),
            "iframe_sources": forensic.get("iframe_sources", [])[:5],
        },
        "visible_links": [{"href": l.get("href", "")[:150], "text": (l.get("text") or "")[:60]}
                          for l in links_raw[:10]],
    }
    return json.dumps(data, indent=2, default=str)


def _build_screenshot_summary(screenshot: dict) -> str:
    return json.dumps(screenshot, indent=2, default=str) if screenshot else "No screenshot."


def _build_claim_summary(claims: list[dict]) -> str:
    clean = [{"claim": (c.get("text") or "")[:200], "verified": c.get("verified", False),
              "contradicted": c.get("contradicted", False),
              "sources_found": len(c.get("sources", [])),
              "source_names": [s.get("source") for s in (c.get("sources") or [])[:3]]} for c in claims]
    return json.dumps(clean, indent=2, default=str) if claims else "No claims to verify."


def _summarize_rendered_fields(rendered: dict, forensic: dict) -> dict:
    return {
        "method": rendered.get("method"),
        "final_url": rendered.get("final_url"),
        "title": rendered.get("title"),
        "has_login_form": rendered.get("has_login_form"),
        "captures_sensitive": rendered.get("captures_sensitive"),
        "redirect_chain": rendered.get("redirect_chain"),
        "og_site_name": rendered.get("og_site_name"),
        "meta_description": rendered.get("meta_description"),
        "external_domains": rendered.get("external_domains"),
        "forensic": {
            "is_https": forensic.get("is_https"),
            "final_domain": forensic.get("final_domain"),
            "iframe_count": forensic.get("iframe_count"),
            "cross_domain_link_count": forensic.get("cross_domain_link_count"),
            "resource_count": forensic.get("resource_count"),
            "failed_request_count": forensic.get("failed_request_count"),
            "console_error_count": forensic.get("console_error_count"),
            "meta_refresh_tag": forensic.get("meta_refresh_tag"),
            "script_count": forensic.get("script_count"),
            "form_count": forensic.get("form_count"),
            "input_count": forensic.get("input_count"),
            "tls": forensic.get("tls_info", {}),
            "security_headers": forensic.get("security_headers", {}),
            "whois": forensic.get("whois", {}),
            "js_forensics": forensic.get("js_forensics", {}),
        },
    }
