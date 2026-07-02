"""Social-media manipulation detector.

Triage : manipulation heuristics + link features on the post text/URL.
Deep   : renders the live post/profile page, analyzes a screenshot via the
         vision model, and asks the reasoning LLM to judge manipulation intent,
         false authority, and fraudulent call-to-action using rich evidence.
"""
from __future__ import annotations

import time

from ..llm import analyze_screenshot, reason_json
from ..preprocessing import heuristics
from ..render import render
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence

_SYS = (
    "You are a market-manipulation analyst reviewing a social-media post about "
    "securities/stocks. Judge whether it manipulates retail investors via false "
    "authority (fake SEBI/exchange/advisor claims), pump-and-dump urgency, guaranteed "
    "returns, or a fraudulent call-to-action (join Telegram/WhatsApp, pay fee, buy now). "
    "Use the rendered page evidence and VISION SCREENSHOT analysis if present.\n\n"
    "CRITICAL CALIBRATION RULES:\n"
    "- A legitimate educational post from a real regulator or exchange (e.g. SEBI's actual "
    "website, NSE's official page) warning about scams is NOT manipulation -> probability < 0.1.\n"
    "- A general market commentary post with no fraudulent CTA is not manipulation.\n"
    "- Manipulation requires a DECEPTIVE element: fake authority claims, guaranteed returns, "
    "urgency to join/transfer, or impersonation of an official entity.\n"
    "- Trust the vision screenshot analysis when a page looks clean and non-deceptive.\n\n"
    "Respond ONLY as JSON with keys: "
    "manipulation_probability (0-1 float), false_authority (bool), suspicious_cta "
    "(string or null), fraud_destination (string or null), explanation (<=60 words)."
)


def _base_probability(req: AnalysisRequest, h: dict) -> float:
    score = h["score"] * 0.65
    for l in req.links:
        if l.suspicious and not l.allowlisted:
            score += min(0.1 * len(l.reasons), 0.3)
    if "financial_lure" in h["categories"]:
        score += 0.12
    if "authority_claim" in h["categories"]:
        score += 0.1
    return max(0.0, min(score, 1.0))


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    h = heuristics.scan(req.raw_input)
    evidence: list[Evidence] = []

    for cat, phrases in h["categories"].items():
        sev = "high" if cat in ("financial_lure", "authority_claim") else "medium"
        evidence.append(Evidence(
            source="social", label=heuristics.CATEGORY_LABELS.get(cat, cat),
            detail="Matched: " + ", ".join(phrases[:4]), weight=0.12, severity=sev))

    for l in req.links:
        if l.suspicious and not l.allowlisted:
            evidence.append(Evidence(
                source="social", label=f"Suspicious linked destination: {l.registered_domain or l.domain}",
                detail="; ".join(l.reasons), weight=0.18, severity="high"))

    prob = _base_probability(req, h)
    fields = {
        "false_authority": "authority_claim" in h["categories"],
        "suspicious_cta": "join a messaging group" if "financial_lure" in h["categories"] else None,
        "manipulation_categories": h["fired"],
    }
    explanation = "Triage: manipulation phrasing + linked-destination features."
    used_llm = False
    used_render = False

    if deep:
        rendered = None
        target = None
        for l in req.links:
            target = l
            break
        if target:
            rendered = render(target.raw)
            used_render = True
            if rendered.get("rendered"):
                if rendered.get("title"):
                    evidence.append(Evidence(
                        source="social", label="Rendered post/page title",
                        detail=rendered["title"][:160], weight=0.04, severity="info"))
                if rendered.get("captures_sensitive"):
                    evidence.append(Evidence(
                        source="social", label="Linked page captures sensitive data",
                        detail=f"Form on {rendered.get('final_url','')} requests credentials/payment.",
                        weight=0.25, severity="high"))
                if rendered.get("cross_domain_redirect"):
                    evidence.append(Evidence(
                        source="social", label="Redirects off-platform",
                        detail=" -> ".join(rendered.get("redirect_chain", [])[:4]),
                        weight=0.15, severity="medium"))

        forensic = rendered.get("forensic", {}) if rendered else {}
        if forensic:
            if forensic.get("is_https") is False:
                evidence.append(Evidence(
                    source="social", label="Linked page served over HTTP",
                    detail="No transport encryption — insecure link destination.",
                    weight=0.1, severity="medium"))
            if forensic.get("cross_domain_link_count", 0) >= 5:
                evidence.append(Evidence(
                    source="social", label=f"Page links to {forensic.get('cross_domain_link_count')} external domains",
                    detail="High number of outbound links — possible gateway or link-farm.",
                    weight=0.08, severity="low"))
            if forensic.get("meta_refresh_tag"):
                evidence.append(Evidence(
                    source="social", label="Meta refresh redirect detected",
                    detail=f"Page uses meta refresh to redirect: {forensic.get('meta_refresh_tag')}",
                    weight=0.15, severity="high"))
            if forensic.get("iframe_count", 0) > 0:
                evidence.append(Evidence(
                    source="social", label=f"Page embeds {forensic.get('iframe_count')} iframe(s)",
                    detail="External content embedded via iframes.",
                    weight=0.08, severity="medium"))

        screenshot_analysis: dict = {}
        if rendered and rendered.get("screenshot_b64"):
            screenshot_analysis, _ = analyze_screenshot(rendered["screenshot_b64"])
            if screenshot_analysis:
                if screenshot_analysis.get("looks_deceptive"):
                    evidence.append(Evidence(
                        source="social", label="Screenshot looks deceptive (vision)",
                        detail=f"Vision model: page visually imitates {screenshot_analysis.get('imitates_brand') or 'a brand'}. "
                               f"{screenshot_analysis.get('notes','')}",
                        weight=0.25, severity="high"))
                elif screenshot_analysis.get("imitates_brand"):
                    evidence.append(Evidence(
                        source="social", label="Brand imitation detected (vision)",
                        detail=f"Vision model: page resembles {screenshot_analysis.get('imitates_brand')} "
                               f"(page_type={screenshot_analysis.get('page_type')}). "
                               f"deceptive={screenshot_analysis.get('looks_deceptive')}. "
                               f"{screenshot_analysis.get('notes','')}",
                        weight=0.12, severity="medium"))
                else:
                    evidence.append(Evidence(
                        source="social", label="Screenshot visually assessed (vision)",
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
                f"captures_sensitive={rendered.get('captures_sensitive')} "
                f"cross_domain_redirect={rendered.get('cross_domain_redirect')} "
                f"external_domains={rendered.get('external_domains')} "
                f"text_excerpt={rendered.get('text_excerpt','')[:700]!r}"
            )
        forensic_summary = "No forensic data."
        if forensic:
            forensic_summary = (
                f"is_https={forensic.get('is_https')} final_domain={forensic.get('final_domain')} "
                f"iframe_count={forensic.get('iframe_count')} "
                f"cross_domain_link_count={forensic.get('cross_domain_link_count')} "
                f"cross_domain_links={[(l.get('href',''), l.get('text','')) for l in forensic.get('cross_domain_links',[])[:5]]} "
                f"resource_count={forensic.get('resource_count')} "
                f"console_errors={forensic.get('console_error_count',0)} "
                f"meta_refresh={forensic.get('meta_refresh_tag')} "
                f"form_count={forensic.get('form_count')} "
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
            f"POST TEXT/URL:\n{req.raw_input[:1800]}\n\n"
            f"DETECTED ENTITIES: {[e.text for e in req.entities]}\n"
            f"LINKS: {[l.raw for l in req.links]}\n"
            f"RENDERED PAGE EVIDENCE:\n{rendered_summary}\n\n"
            f"BROWSER FORENSIC DATA:\n{forensic_summary}\n\n"
            f"VISION SCREENSHOT ANALYSIS:\n{screenshot_summary}\n"
        )

        def _fallback():
            return {
                "manipulation_probability": prob,
                "false_authority": fields["false_authority"],
                "suspicious_cta": fields["suspicious_cta"],
                "fraud_destination": next((l.registered_domain for l in req.links if l.suspicious and not l.allowlisted), None),
                "explanation": "Rule-based: "
                + ("false-authority + " if fields["false_authority"] else "")
                + ("financial lure + urgency detected." if h["fired"] else "limited manipulation signals."),
            }

        data, used_llm = reason_json(_SYS, user, _fallback)
        if used_llm:
            try:
                prob = float(data.get("manipulation_probability", prob))
            except Exception:
                pass
        else:
            prob = _base_probability(req, h)
        prob = max(0.0, min(prob, 1.0))
        fields["false_authority"] = bool(data.get("false_authority", fields["false_authority"]))
        fields["suspicious_cta"] = data.get("suspicious_cta", fields["suspicious_cta"])
        fields["fraud_destination"] = data.get("fraud_destination")
        explanation = data.get("explanation", explanation)
        if rendered:
            fields["rendered"] = {
                "method": rendered.get("method"),
                "final_url": rendered.get("final_url"),
                "title": rendered.get("title"),
                "captures_sensitive": rendered.get("captures_sensitive"),
                "og_site_name": rendered.get("og_site_name"),
                "meta_description": rendered.get("meta_description"),
                "external_domains": rendered.get("external_domains"),
            }
            if forensic:
                fields["rendered"]["forensic"] = {
                    "is_https": forensic.get("is_https"),
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
                }

    label = "Likely manipulation" if prob >= 0.6 else ("Suspicious" if prob >= 0.35 else "Low manipulation risk")
    return DetectorResult(
        name="social", channel=ChannelType.SOCIAL, probability=round(prob, 3),
        label=label, fields=fields, evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000), used_llm=used_llm, used_render=used_render,
    )
