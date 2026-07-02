"""Phishing / impersonation detector.

Triage : manipulation heuristics + URL lexical features (cheap, no network).
Deep   : renders the most suspicious link (Playwright/HTTP), analyzes a
         screenshot via the vision model, and asks the reasoning LLM to judge
         rendered impersonation + credential capture using rich evidence.
"""
from __future__ import annotations

import time

from ..llm import analyze_screenshot, reason_json
from ..preprocessing import heuristics
from ..render import render
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence

_SYS = (
    "You are a securities-market phishing analyst. Given a message, the RENDERED "
    "evidence of any linked page, page metadata, and a VISION MODEL'S visual assessment "
    "of the page screenshot, judge whether this is a phishing / impersonation attempt "
    "targeting retail investors.\n\n"
    "CRITICAL CALIBRATION RULES:\n"
    "- A login/password form on a brand's REAL verified domain (e.g. kite.zerodha.com/login, "
    "groww.in/login, sebi.gov.in) is NORMAL and NOT phishing -> phishing_probability < 0.15.\n"
    "- Phishing means the page DETECTIVELY imitates a brand on a DIFFERENT or lookalike domain, "
    "OR captures sensitive data on a non-brand domain (typosquat, IP address, .xyz/.top/.click, shortener).\n"
    "- Trust the vision model when it says a page does NOT look deceptive. A clean, professional "
    "broker login page on the correct domain with no deceptive visual imitation is legit.\n"
    "- A page that merely MENTIONS SEBI/NSE/RBI by name in a news article or educational post "
    "is NOT phishing.\n\n"
    "Consider: brand impersonation, domain mismatch, credential/OTP/payment capture, "
    "redirect chains, page metadata (og_site_name, meta_description), and the VISION "
    "SCREENSHOT analysis (imitates_brand, looks_deceptive, page_type).\n"
    "Respond ONLY as JSON with keys: phishing_probability (0-1 float), impersonated_entity "
    "(string or null), domain_mismatch (bool), credential_capture (bool), "
    "explanation (<=60 words)."
)


def _pick_link(req: AnalysisRequest):
    if not req.links:
        return None
    ranked = sorted(
        req.links,
        key=lambda l: (l.allowlisted, -len(l.reasons)),
    )
    for l in ranked:
        if not l.allowlisted:
            return l
    return ranked[0]


def _base_probability(req: AnalysisRequest, h: dict) -> float:
    score = h["score"] * 0.6
    link = _pick_link(req)
    if link and not link.allowlisted:
        score += min(0.12 * len(link.reasons), 0.4)
    if link and link.allowlisted:
        score -= 0.25
    crit = max((e.criticality for e in req.entities), default=0.0)
    if crit >= 0.9 and link and not link.allowlisted:
        score += 0.15
    return max(0.0, min(score, 1.0))


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    h = heuristics.scan(req.raw_input)
    evidence: list[Evidence] = []

    for cat, phrases in h["categories"].items():
        evidence.append(
            Evidence(
                source="phishing",
                label=heuristics.CATEGORY_LABELS.get(cat, cat),
                detail="Matched: " + ", ".join(phrases[:4]),
                weight=0.12,
                severity="medium",
            )
        )

    link = _pick_link(req)
    if link and not link.allowlisted and link.reasons:
        evidence.append(
            Evidence(
                source="phishing",
                label=f"Suspicious link: {link.registered_domain or link.domain}",
                detail="; ".join(link.reasons),
                weight=0.2,
                severity="high",
            )
        )
    if link and link.allowlisted:
        evidence.append(
            Evidence(
                source="phishing",
                label=f"Link on official allowlist: {link.registered_domain}",
                detail="Destination domain is a known official source.",
                weight=-0.3,
                severity="info",
            )
        )

    prob = _base_probability(req, h)
    impersonated = req.entities[0].text if req.entities else None
    fields = {
        "impersonated_entity": impersonated,
        "domain_mismatch": bool(link and not link.allowlisted and any("brand token" in r for r in link.reasons)),
        "credential_capture": "credential_request" in h["categories"],
        "manipulation_categories": h["fired"],
    }
    explanation = "Triage: manipulation phrasing and URL lexical features."
    used_llm = False
    used_render = False

    if deep:
        rendered = None
        if link:  # Render ALL links — even allowlisted ones get forensic analysis
            rendered = render(link.raw)
            used_render = True
            if rendered.get("rendered"):
                if rendered.get("cross_domain_redirect"):
                    evidence.append(Evidence(
                        source="phishing", label="Cross-domain redirect chain",
                        detail=" -> ".join(rendered.get("redirect_chain", [])[:4]),
                        weight=0.2, severity="high"))
                if rendered.get("captures_sensitive"):
                    evidence.append(Evidence(
                        source="phishing", label="Rendered page captures credentials",
                        detail=f"Form(s) request password/OTP/payment on {rendered.get('final_url','')}",
                        weight=0.3, severity="high"))
                    fields["credential_capture"] = True
                if rendered.get("title"):
                    evidence.append(Evidence(
                        source="phishing", label="Rendered page title",
                        detail=rendered["title"][:160], weight=0.05, severity="info"))

        forensic = rendered.get("forensic", {}) if rendered else {}
        if forensic:
            if forensic.get("is_https") is False:
                evidence.append(Evidence(
                    source="phishing", label="Page served over HTTP (not HTTPS)",
                    detail=f"{rendered.get('final_url','')} uses plain HTTP — no transport encryption.",
                    weight=0.12, severity="medium"))
            if forensic.get("console_error_count", 0) >= 3:
                evidence.append(Evidence(
                    source="phishing", label=f"Browser console errors ({forensic.get('console_error_count')})",
                    detail=f"Page triggered {forensic.get('console_error_count')} console errors — "
                           "possible broken or hastily-built page.",
                    weight=0.08, severity="low"))
            if forensic.get("failed_request_count", 0) >= 2:
                evidence.append(Evidence(
                    source="phishing", label=f"Failed network requests ({forensic.get('failed_request_count')})",
                    detail="Page attempted to load resources that failed — may indicate broken infrastructure.",
                    weight=0.06, severity="low"))
            if forensic.get("iframe_count", 0) > 0:
                iframe_srcs = forensic.get("iframe_sources", [])
                evidence.append(Evidence(
                    source="phishing", label=f"Page contains {forensic.get('iframe_count')} iframe(s)",
                    detail=f"Embedded frame sources: {', '.join(iframe_srcs[:3])}" if iframe_srcs
                    else "Page embeds external content via iframes.",
                    weight=0.1, severity="medium"))
            if forensic.get("cross_domain_link_count", 0) >= 5:
                evidence.append(Evidence(
                    source="phishing", label=f"Page links to {forensic.get('cross_domain_link_count')} external domains",
                    detail="High number of cross-domain links — may be a gateway or redirect landing page.",
                    weight=0.08, severity="low"))
            if forensic.get("meta_refresh_tag"):
                evidence.append(Evidence(
                    source="phishing", label="Meta refresh redirect detected",
                    detail=f"Page uses meta refresh to redirect: {forensic.get('meta_refresh_tag')}",
                    weight=0.15, severity="high"))
            if forensic.get("resource_count", 0) < 3:
                evidence.append(Evidence(
                    source="phishing", label="Sparsely populated page",
                    detail=f"Page loads only {forensic.get('resource_count')} resources — "
                           "may be a bare credential-harvesting form.",
                    weight=0.1, severity="medium"))

        screenshot_analysis: dict = {}
        if rendered and rendered.get("screenshot_b64"):
            screenshot_analysis, _ = analyze_screenshot(rendered["screenshot_b64"])
            if screenshot_analysis:
                if screenshot_analysis.get("looks_deceptive"):
                    evidence.append(Evidence(
                        source="phishing", label="Screenshot looks deceptive (vision)",
                        detail=f"Vision model: page visually imitates {screenshot_analysis.get('imitates_brand') or 'a brand'}. "
                               f"{screenshot_analysis.get('notes','')}",
                        weight=0.25, severity="high"))
                elif screenshot_analysis.get("imitates_brand"):
                    evidence.append(Evidence(
                        source="phishing", label="Brand imitation detected (vision)",
                        detail=f"Vision model: page resembles {screenshot_analysis.get('imitates_brand')} "
                               f"(page_type={screenshot_analysis.get('page_type')}). "
                               f"deceptive={screenshot_analysis.get('looks_deceptive')}. "
                               f"{screenshot_analysis.get('notes','')}",
                        weight=0.15, severity="medium"))
                else:
                    evidence.append(Evidence(
                        source="phishing", label="Screenshot visually assessed (vision)",
                        detail=f"Vision model: page_type={screenshot_analysis.get('page_type')}, "
                               f"deceptive={screenshot_analysis.get('looks_deceptive')}. "
                               f"{screenshot_analysis.get('notes','')}",
                        weight=0.0, severity="info"))
                fields["screenshot_vision"] = {k: v for k, v in screenshot_analysis.items() if v}

        rendered_summary = "None"
        if rendered and rendered.get("rendered"):
            rendered_summary = (
                f"final_url={rendered.get('final_url')} title={rendered.get('title')!r} "
                f"og_site_name={rendered.get('og_site_name')!r} "
                f"meta_description={rendered.get('meta_description','')[:120]!r} "
                f"has_login_form={rendered.get('has_login_form')} "
                f"captures_sensitive={rendered.get('captures_sensitive')} "
                f"has_password={rendered.get('has_login_form')} "
                f"external_domains={rendered.get('external_domains')} "
                f"redirect_chain={rendered.get('redirect_chain')} "
                f"cross_domain_redirect={rendered.get('cross_domain_redirect')} "
                f"text_excerpt={rendered.get('text_excerpt','')[:600]!r}"
            )
        forensic_summary = "No forensic data."
        if forensic:
            forensic_summary = (
                f"is_https={forensic.get('is_https')} protocol={forensic.get('protocol')} "
                f"final_domain={forensic.get('final_domain')} "
                f"iframe_count={forensic.get('iframe_count')} "
                f"iframe_sources={forensic.get('iframe_sources',[])} "
                f"cross_domain_link_count={forensic.get('cross_domain_link_count')} "
                f"cross_domain_links={[(l.get('href',''), l.get('text','')) for l in forensic.get('cross_domain_links',[])[:5]]} "
                f"resource_count={forensic.get('resource_count')} "
                f"failed_requests={forensic.get('failed_requests',[])[:5]} "
                f"console_errors={forensic.get('console_error_count',0)} "
                f"meta_refresh={forensic.get('meta_refresh_tag')} "
                f"script_count={forensic.get('script_count')} "
                f"form_count={forensic.get('form_count')} "
                f"input_count={forensic.get('input_count')} "
                f"link_domain_pairs={[(l.get('href',''), l.get('text','')[:50]) for l in forensic.get('all_links',[])[:10]]}"
            )
        screenshot_summary = "No screenshot available."
        if screenshot_analysis:
            screenshot_summary = (
                f"page_type={screenshot_analysis.get('page_type')} "
                f"imitates_brand={screenshot_analysis.get('imitates_brand')} "
                f"is_login_or_payment={screenshot_analysis.get('is_login_or_payment')} "
                f"looks_deceptive={screenshot_analysis.get('looks_deceptive')} "
                f"notes={screenshot_analysis.get('notes')}"
            )
        user = (
            f"MESSAGE:\n{req.raw_input[:1800]}\n\n"
            f"DETECTED ENTITIES: {[e.text for e in req.entities]}\n"
            f"LINK: {link.raw if link else 'none'} (allowlisted={link.allowlisted if link else 'n/a'}, "
            f"reasons={link.reasons if link else []})\n"
            f"RENDERED PAGE EVIDENCE:\n{rendered_summary}\n\n"
            f"BROWSER FORENSIC DATA:\n{forensic_summary}\n\n"
            f"VISION SCREENSHOT ANALYSIS:\n{screenshot_summary}\n"
        )

        def _fallback():
            return {
                "phishing_probability": prob,
                "impersonated_entity": impersonated,
                "domain_mismatch": fields["domain_mismatch"],
                "credential_capture": fields["credential_capture"],
                "explanation": "Rule-based verdict (LLM unavailable): "
                + ("credential-capture + suspicious link. " if fields["credential_capture"] else "")
                + ("manipulation phrasing present." if h["fired"] else "limited signals."),
            }

        data, used_llm = reason_json(_SYS, user, _fallback)
        if used_llm:
            try:
                prob = float(data.get("phishing_probability", prob))
            except Exception:
                pass
        else:
            prob = _base_probability(req, h)
        prob = max(0.0, min(prob, 1.0))
        fields["impersonated_entity"] = data.get("impersonated_entity", impersonated)
        fields["domain_mismatch"] = bool(data.get("domain_mismatch", fields["domain_mismatch"]))
        fields["credential_capture"] = bool(data.get("credential_capture", fields["credential_capture"]))
        explanation = data.get("explanation", explanation)
        if rendered:
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
            }
            if forensic:
                fields["rendered"]["forensic"] = {
                    "is_https": forensic.get("is_https"),
                    "protocol": forensic.get("protocol"),
                    "final_domain": forensic.get("final_domain"),
                    "iframe_count": forensic.get("iframe_count"),
                    "cross_domain_link_count": forensic.get("cross_domain_link_count"),
                    "cross_domain_links": forensic.get("cross_domain_links", [])[:5],
                    "resource_count": forensic.get("resource_count"),
                    "failed_request_count": forensic.get("failed_request_count"),
                    "console_error_count": forensic.get("console_error_count"),
                    "meta_refresh_tag": forensic.get("meta_refresh_tag"),
                    "script_count": forensic.get("script_count"),
                    "form_count": forensic.get("form_count"),
                    "input_count": forensic.get("input_count"),
                }

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
