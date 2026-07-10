"""Phishing / impersonation detector — LLM-first scoring.

No regex heuristics drive the score. Flow:
  1. Intent LLM: classifies message intent, extracts claims, identifies impersonation
  2. Playwright: renders linked pages, collects forensic evidence
  3. Vision model: analyzes page screenshots for brand imitation
  4. Web search: verifies factual claims against multiple legitimate sources
  5. Verdict LLM: synthesizes ALL evidence into a single 0-1 probability

The LLM is the ONLY scoring authority. No static rules, floors, or caps.
"""
from __future__ import annotations

import time
from typing import Any

from ..intent import analyze_message
from ..llm import analyze_screenshot, reason_json
from ..prompts import load as load_prompt
from ..render import render
from ..search import extract_claims, verify_claims_sync
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence


def _pick_link(req: AnalysisRequest):
    if not req.links:
        return None
    ranked = sorted(req.links, key=lambda l: (l.allowlisted, -len(l.reasons)))
    for l in ranked:
        if not l.allowlisted:
            return l
    return ranked[0]


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

    evidence.append(Evidence(
        source="intent", label="Message intent analysis",
        detail=f"Intent: {intent.get('intent', 'unknown')}. "
               f"Impersonation: {intent.get('impersonation_target', 'none')}. "
               f"{intent.get('explanation', '')}",
        weight=0.0, severity="info"))

    if intent.get("urgency_detected"):
        evidence.append(Evidence(
            source="intent", label="Urgency or threat detected",
            detail="Message contains artificial urgency or threat of account action.",
            weight=0.1, severity="medium"))
    if intent.get("credential_request_detected"):
        evidence.append(Evidence(
            source="intent", label="Credential request detected",
            detail="Message actively asks for OTP, password, KYC, or credentials.",
            weight=0.15, severity="high" if intent.get("urgency_detected") else "medium"))
    if intent.get("authority_claim_detected"):
        evidence.append(Evidence(
            source="intent", label="Authority claim detected",
            detail="Message claims or implies official regulatory/broker authority.",
            weight=0.08, severity="low"))

    prob = intent.get("phishing_probability", 0.25)
    impersonated = intent.get("impersonation_target")
    fields: dict[str, Any] = {
        "impersonated_entity": impersonated,
        "intent": intent.get("intent"),
        "domain_mismatch": False,
        "credential_capture": intent.get("credential_request_detected", False),
    }
    explanation = intent.get("explanation", "")

    if link:
        rendered = render(link.raw)
        used_render = True

        if rendered.get("rendered"):
            if rendered.get("cross_domain_redirect"):
                evidence.append(Evidence(
                    source="phishing", label="Cross-domain redirect chain",
                    detail=" -> ".join(rendered.get("redirect_chain", [])[:4]),
                    weight=0.15, severity="high"))
            if rendered.get("captures_sensitive"):
                evidence.append(Evidence(
                    source="phishing", label="Page captures sensitive data",
                    detail=f"Form(s) request password/OTP/payment on {rendered.get('final_url','')}",
                    weight=0.2, severity="high"))
                fields["credential_capture"] = True
            if rendered.get("title"):
                evidence.append(Evidence(
                    source="phishing", label="Rendered page title",
                    detail=rendered["title"][:160], weight=0.03, severity="info"))

            forensic = rendered.get("forensic", {})
            if forensic:
                _add_forensic_evidence(evidence, forensic, rendered)

                fields["rendered"] = {
                    "method": rendered.get("method"),
                    "final_url": rendered.get("final_url"),
                    "title": rendered.get("title"),
                    "has_login_form": rendered.get("has_login_form"),
                    "captures_sensitive": rendered.get("captures_sensitive"),
                    "redirect_chain": rendered.get("redirect_chain"),
                    "og_site_name": rendered.get("og_site_name"),
                    "meta_description": rendered.get("meta_description"),
                    "external_domains": rendered.get("external_domains"),
                    "forensic": _summarize_forensic(forensic),
                }

            screenshot_analysis: dict = {}
            if rendered.get("screenshot_b64"):
                screenshot_analysis, _ = analyze_screenshot(rendered["screenshot_b64"])
                _add_screenshot_evidence(evidence, screenshot_analysis, fields)

            claims = intent.get("claims_to_verify", []) or extract_claims(req.raw_input)
            claim_results = verify_claims_sync(claims)
            _add_claim_evidence(evidence, claim_results)

            rendered_summary = _build_rendered_summary(rendered)
            forensic_summary = _build_forensic_summary(forensic)
            screenshot_summary = _build_screenshot_summary(screenshot_analysis)
            claim_summary = _build_claim_summary(claim_results)

            user = (
                f"MESSAGE:\n{req.raw_input[:2000]}\n\n"
                f"INTENT ANALYSIS:\n"
                f"  classification={intent.get('intent')} "
                f"impersonation={impersonated} "
                f"credential_request={intent.get('credential_request_detected')} "
                f"urgency={intent.get('urgency_detected')} "
                f"explanation={intent.get('explanation')}\n\n"
                f"RENDERED PAGE:\n{rendered_summary}\n\n"
                f"FORENSIC DATA:\n{forensic_summary}\n\n"
                f"SCREENSHOT ANALYSIS:\n{screenshot_summary}\n\n"
                f"CLAIM VERIFICATION:\n{claim_summary}\n\n"
                f"LINK: {link.raw} (allowlisted={link.allowlisted})\n"
            )

            def _neutral():
                return {
                    "phishing_probability": prob,
                    "impersonated_entity": impersonated,
                    "domain_mismatch": fields.get("domain_mismatch", False),
                    "credential_capture": fields.get("credential_capture", False),
                    "key_evidence": ["LLM unavailable — heuristic fallback"],
                    "explanation": "Limited assessment without LLM.",
                    "recommended_action": "verify",
                }

            data, used_llm = reason_json(load_prompt("phishing_verdict.txt"), user, _neutral)
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
                evidence.append(Evidence(
                    source="verdict", label="Key evidence",
                    detail=str(k)[:200], weight=0.1, severity="info"))

    label = "Likely phishing" if prob >= 0.6 else ("Suspicious" if prob >= 0.35 else "Low phishing risk")
    return DetectorResult(
        name="phishing",
        channel=ChannelType.EMAIL if req.channel_type != ChannelType.URL else ChannelType.URL,
        probability=round(prob, 3),
        label=label,
        fields=fields,
        evidence=evidence,
        explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000),
        used_llm=used_llm,
        used_render=used_render,
    )


def _add_forensic_evidence(evidence: list[Evidence], forensic: dict, rendered: dict) -> None:
    tls = forensic.get("tls_info", {})
    sec = forensic.get("security_headers", {})
    js = forensic.get("js_forensics", {})

    if forensic.get("is_https") is False:
        evidence.append(Evidence(
            source="forensic", label="No HTTPS",
            detail="Page served over plain HTTP — no transport encryption.",
            weight=0.1, severity="medium"))
    if tls.get("available") and tls.get("not_before"):
        evidence.append(Evidence(
            source="forensic", label="TLS Certificate",
            detail=f"Issuer: {tls.get('issuer', {})}, valid from {tls.get('not_before')}.",
            weight=0.02, severity="info"))
    if not sec.get("csp"):
        evidence.append(Evidence(
            source="forensic", label="Missing CSP header",
            detail="No Content-Security-Policy — page has no script/image source restrictions.",
            weight=0.05, severity="low"))
    if not sec.get("hsts"):
        evidence.append(Evidence(
            source="forensic", label="Missing HSTS header",
            detail="No Strict-Transport-Security header.",
            weight=0.03, severity="low"))
    if forensic.get("console_error_count", 0) >= 3:
        evidence.append(Evidence(
            source="forensic", label=f"Console errors ({forensic.get('console_error_count')})",
            detail=f"Page triggered {forensic.get('console_error_count')} browser console errors.",
            weight=0.06, severity="low"))
    if forensic.get("failed_request_count", 0) >= 3:
        evidence.append(Evidence(
            source="forensic", label=f"Failed network requests ({forensic.get('failed_request_count')})",
            detail="Multiple resources failed to load — possibly broken infrastructure.",
            weight=0.08, severity="medium"))
    if forensic.get("meta_refresh_tag"):
        evidence.append(Evidence(
            source="forensic", label="Meta refresh redirect",
            detail=f"Page uses meta refresh: {forensic.get('meta_refresh_tag')}",
            weight=0.15, severity="high"))
    if forensic.get("iframe_count", 0) > 0:
        iframe_srcs = forensic.get("iframe_sources", [])
        evidence.append(Evidence(
            source="forensic", label=f"Page contains {forensic.get('iframe_count')} iframe(s)",
            detail=f"Embedded frames: {', '.join(iframe_srcs[:3])}" if iframe_srcs else "External iframes present.",
            weight=0.08, severity="medium"))
    if forensic.get("cross_domain_link_count", 0) >= 5:
        evidence.append(Evidence(
            source="forensic", label=f"Many cross-domain links ({forensic.get('cross_domain_link_count')})",
            detail="High number of outbound links to external domains.",
            weight=0.05, severity="low"))
    whois = forensic.get("whois", {})
    if whois.get("creation_date"):
        evidence.append(Evidence(
            source="forensic", label="Domain registration",
            detail=f"Domain registered: {whois.get('creation_date')}. Registrar: {whois.get('registrar', 'unknown')}.",
            weight=0.02, severity="info"))
    if js.get("hidden_inputs") and len(js.get("hidden_inputs", [])) >= 3:
        evidence.append(Evidence(
            source="forensic", label="Multiple hidden form fields",
            detail=f"{len(js.get('hidden_inputs'))} hidden input fields — possible phishing kit.",
            weight=0.1, severity="medium"))
    if forensic.get("dialogues"):
        evidence.append(Evidence(
            source="forensic", label=f"Browser dialogs triggered ({len(forensic.get('dialogues'))})",
            detail=f"Page attempted popups/dialogs: {'; '.join(forensic.get('dialogues', [])[:3])}",
            weight=0.1, severity="medium"))
    if forensic.get("popup_count", 0) > 0:
        evidence.append(Evidence(
            source="forensic", label=f"Popups detected ({forensic.get('popup_count')})",
            detail="Page attempted to open popup windows.",
            weight=0.12, severity="medium"))


def _add_screenshot_evidence(evidence: list[Evidence], screenshot: dict, fields: dict) -> None:
    if not screenshot:
        return
    if screenshot.get("looks_deceptive"):
        evidence.append(Evidence(
            source="vision", label="Screenshot looks deceptive",
            detail=f"Vision model: page visually imitates {screenshot.get('imitates_brand') or 'a brand'}. "
                   f"{screenshot.get('notes', '')}",
            weight=0.25, severity="high"))
    elif screenshot.get("imitates_brand"):
        evidence.append(Evidence(
            source="vision", label="Brand resemblance detected",
            detail=f"Vision: page resembles {screenshot.get('imitates_brand')} "
                   f"({screenshot.get('page_type')}). Deceptive: {screenshot.get('looks_deceptive')}. "
                   f"{screenshot.get('notes', '')}",
            weight=0.05, severity="info"))
    else:
        evidence.append(Evidence(
            source="vision", label="Screenshot visually assessed",
            detail=f"Vision: page_type={screenshot.get('page_type')}, "
                   f"deceptive={screenshot.get('looks_deceptive')}. {screenshot.get('notes', '')}",
            weight=0.0, severity="info"))
    fields["screenshot_vision"] = {k: v for k, v in screenshot.items() if v}


def _add_claim_evidence(evidence: list[Evidence], claim_results: list[dict]) -> None:
    for claim in claim_results:
        if claim.get("verified"):
            evidence.append(Evidence(
                source="search", label="Claim verified",
                detail=f"'{claim.get('text', '')[:120]}' — verified by {len(claim.get('sources', []))} sources.",
                weight=-0.1, severity="info"))
        elif claim.get("contradicted"):
            evidence.append(Evidence(
                source="search", label="Claim CONTRADICTED",
                detail=f"'{claim.get('text', '')[:120]}' — contradicted by official sources.",
                weight=0.3, severity="high"))
        else:
            evidence.append(Evidence(
                source="search", label="Claim unverified",
                detail=f"'{claim.get('text', '')[:120]}' — could not verify from any source.",
                weight=0.05, severity="low"))


def _build_rendered_summary(rendered: dict) -> str:
    if not rendered or not rendered.get("rendered"):
        return "No rendered page."
    return (
        f"final_url={rendered.get('final_url')} title={rendered.get('title')!r} "
        f"og_site_name={rendered.get('og_site_name')!r} "
        f"meta_description={rendered.get('meta_description', '')[:150]!r} "
        f"has_login_form={rendered.get('has_login_form')} "
        f"captures_sensitive={rendered.get('captures_sensitive')} "
        f"redirect_chain={rendered.get('redirect_chain')} "
        f"cross_domain={rendered.get('cross_domain_redirect')} "
        f"text_excerpt={rendered.get('text_excerpt', '')[:600]!r}"
    )


def _build_forensic_summary(forensic: dict) -> str:
    if not forensic:
        return "No forensic data."
    tls = forensic.get("tls_info", {})
    sec = forensic.get("security_headers", {})
    whois = forensic.get("whois", {})
    js = forensic.get("js_forensics", {})
    return (
        f"is_https={forensic.get('is_https')} final_domain={forensic.get('final_domain')} "
        f"console_errors={forensic.get('console_error_count', 0)} "
        f"failed_requests={forensic.get('failed_request_count', 0)} "
        f"iframes={forensic.get('iframe_count', 0)} "
        f"cross_domain_links={forensic.get('cross_domain_link_count', 0)} "
        f"meta_refresh={forensic.get('meta_refresh_tag')} "
        f"form_count={forensic.get('form_count')} input_count={forensic.get('input_count')} "
        f"resource_count={forensic.get('resource_count')} "
        f"TLS: protocol={tls.get('protocol')} issuer={tls.get('issuer', {})} "
        f"not_before={tls.get('not_before')} "
        f"CSP={'yes' if sec.get('csp') else 'no'} "
        f"HSTS={'yes' if sec.get('hsts') else 'no'} "
        f"WHOIS: created={whois.get('creation_date')} "
        f"registrar={whois.get('registrar')} "
        f"JS: hidden_inputs={len(js.get('hidden_inputs', []))} "
        f"cookies={js.get('cookie_count', 0)} "
    )


def _build_screenshot_summary(screenshot: dict) -> str:
    if not screenshot:
        return "No screenshot."
    return (
        f"page_type={screenshot.get('page_type')} "
        f"imitates_brand={screenshot.get('imitates_brand')} "
        f"is_login_or_payment={screenshot.get('is_login_or_payment')} "
        f"looks_deceptive={screenshot.get('looks_deceptive')} "
        f"notes={screenshot.get('notes')}"
    )


def _build_claim_summary(claims: list[dict]) -> str:
    if not claims:
        return "No claims to verify."
    lines = []
    for c in claims:
        status = "VERIFIED" if c.get("verified") else ("CONTRADICTED" if c.get("contradicted") else "UNVERIFIED")
        lines.append(f"[{status}] {c.get('text', '')[:150]}")
    return "\n".join(lines)


def _summarize_forensic(forensic: dict) -> dict:
    return {
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
    } if forensic else {}
