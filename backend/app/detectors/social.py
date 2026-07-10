"""Social-media manipulation detector — LLM-first scoring.

Same pattern as phishing.py: intent LLM → Playwright → vision → search → verdict.
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


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    used_llm = False
    used_render = False

    entities_list = [e.text for e in req.entities]

    intent = analyze_message(req.raw_input, entities_list)
    used_llm = True

    evidence.append(Evidence(
        source="intent", label="Message intent analysis",
        detail=f"Intent: {intent.get('intent', 'unknown')}. "
               f"{intent.get('explanation', '')}",
        weight=0.0, severity="info"))

    if intent.get("financial_lure_detected"):
        evidence.append(Evidence(
            source="intent", label="Financial lure detected",
            detail="Message contains guaranteed returns, insider tips, or unrealistic profit claims.",
            weight=0.15, severity="high"))
    if intent.get("authority_claim_detected"):
        evidence.append(Evidence(
            source="intent", label="False authority claim",
            detail="Message claims official or regulatory authority.",
            weight=0.12, severity="medium"))
    if intent.get("urgency_detected"):
        evidence.append(Evidence(
            source="intent", label="Urgency detected",
            detail="Message uses artificial urgency or scarcity.",
            weight=0.08, severity="medium"))

    prob = intent.get("phishing_probability", 0.25)
    fields: dict[str, Any] = {
        "false_authority": intent.get("authority_claim_detected", False),
        "suspicious_cta": "join a messaging group" if intent.get("financial_lure_detected") else None,
        "intent": intent.get("intent"),
    }
    explanation = intent.get("explanation", "")

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
                    detail=rendered["title"][:160], weight=0.03, severity="info"))
            if rendered.get("captures_sensitive"):
                evidence.append(Evidence(
                    source="social", label="Linked page captures sensitive data",
                    detail=f"Form on {rendered.get('final_url','')} requests credentials/payment.",
                    weight=0.2, severity="high"))
            if rendered.get("cross_domain_redirect"):
                evidence.append(Evidence(
                    source="social", label="Redirects off-platform",
                    detail=" -> ".join(rendered.get("redirect_chain", [])[:4]),
                    weight=0.12, severity="medium"))

            forensic = rendered.get("forensic", {})
            if forensic:
                if forensic.get("is_https") is False:
                    evidence.append(Evidence(
                        source="social", label="Linked page served over HTTP",
                        detail="No transport encryption — insecure link destination.",
                        weight=0.08, severity="medium"))
                if forensic.get("cross_domain_link_count", 0) >= 5:
                    evidence.append(Evidence(
                        source="social", label=f"Page links to {forensic.get('cross_domain_link_count')} external domains",
                        detail="High number of outbound links — possible gateway or link-farm.",
                        weight=0.06, severity="low"))
                if forensic.get("meta_refresh_tag"):
                    evidence.append(Evidence(
                        source="social", label="Meta refresh redirect detected",
                        detail=f"Page uses meta refresh to redirect: {forensic.get('meta_refresh_tag')}",
                        weight=0.15, severity="high"))
                if forensic.get("iframe_count", 0) > 0:
                    evidence.append(Evidence(
                        source="social", label=f"Page embeds {forensic.get('iframe_count')} iframe(s)",
                        detail="External content embedded via iframes.",
                        weight=0.06, severity="medium"))

                fields["rendered"] = {
                    "method": rendered.get("method"),
                    "final_url": rendered.get("final_url"),
                    "title": rendered.get("title"),
                    "captures_sensitive": rendered.get("captures_sensitive"),
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
                        "tls": forensic.get("tls_info", {}),
                        "whois": forensic.get("whois", {}),
                    } if forensic else {},
                }

            screenshot_analysis: dict = {}
            if rendered.get("screenshot_b64"):
                screenshot_analysis, _ = analyze_screenshot(rendered["screenshot_b64"])
                if screenshot_analysis:
                    if screenshot_analysis.get("looks_deceptive"):
                        evidence.append(Evidence(
                            source="vision", label="Screenshot looks deceptive",
                            detail=f"Vision: page visually imitates {screenshot_analysis.get('imitates_brand') or 'brand'}. "
                                   f"{screenshot_analysis.get('notes', '')}",
                            weight=0.2, severity="high"))
                    else:
                        evidence.append(Evidence(
                            source="vision", label="Screenshot assessed",
                            detail=f"Vision: page_type={screenshot_analysis.get('page_type')}, "
                                   f"deceptive={screenshot_analysis.get('looks_deceptive')}",
                            weight=0.0, severity="info"))
                    fields["screenshot_vision"] = {k: v for k, v in screenshot_analysis.items() if v}

            claims = intent.get("claims_to_verify", []) or extract_claims(req.raw_input)
            claim_results = verify_claims_sync(claims)
            for claim in claim_results:
                if claim.get("verified"):
                    evidence.append(Evidence(
                        source="search", label="Claim verified",
                        detail=f"'{claim.get('text', '')[:120]}' — verified by {len(claim.get('sources', []))} sources.",
                        weight=-0.1, severity="info"))
                elif claim.get("contradicted"):
                    evidence.append(Evidence(
                        source="search", label="Claim CONTRADICTED",
                        detail=f"'{claim.get('text', '')[:120]}' — contradicted by sources.",
                        weight=0.25, severity="high"))

            rendered_summary = (
                f"final_url={rendered.get('final_url')} title={rendered.get('title')!r} "
                f"captures_sensitive={rendered.get('captures_sensitive')} "
                f"cross_domain={rendered.get('cross_domain_redirect')} "
                f"text_excerpt={rendered.get('text_excerpt', '')[:600]!r}"
            ) if rendered.get("rendered") else "No rendered page."

            screenshot_summary = (
                f"page_type={screenshot_analysis.get('page_type')} "
                f"imitates_brand={screenshot_analysis.get('imitates_brand')} "
                f"looks_deceptive={screenshot_analysis.get('looks_deceptive')}"
            ) if screenshot_analysis else "No screenshot."

            user = (
                f"POST TEXT:\n{req.raw_input[:2000]}\n\n"
                f"INTENT: {intent.get('intent')} "
                f"financial_lure={intent.get('financial_lure_detected')} "
                f"authority={intent.get('authority_claim_detected')}\n"
                f"RENDERED PAGE:\n{rendered_summary}\n\n"
                f"SCREENSHOT:\n{screenshot_summary}\n"
            )

            def _neutral():
                return {
                    "manipulation_probability": prob,
                    "false_authority": fields.get("false_authority", False),
                    "suspicious_cta": fields.get("suspicious_cta"),
                    "fraud_destination": target.registered_domain if target else None,
                    "explanation": "Limited assessment without LLM.",
                }

            data, used_llm = reason_json(load_prompt("social_verdict.txt"), user, _neutral)
            try:
                prob = float(data.get("manipulation_probability", prob))
            except Exception:
                pass
            prob = max(0.0, min(prob, 1.0))

            fields["false_authority"] = bool(data.get("false_authority", False))
            fields["suspicious_cta"] = data.get("suspicious_cta")
            fields["fraud_destination"] = data.get("fraud_destination")
            explanation = data.get("explanation", explanation)
            for k in data.get("key_evidence", [])[:5]:
                evidence.append(Evidence(
                    source="verdict", label="Key evidence",
                    detail=str(k)[:200], weight=0.1, severity="info"))

    label = "Likely manipulation" if prob >= 0.6 else ("Suspicious" if prob >= 0.35 else "Low manipulation risk")
    return DetectorResult(
        name="social", channel=ChannelType.SOCIAL, probability=round(prob, 3),
        label=label, fields=fields, evidence=evidence, explanation=explanation,
        latency_ms=int((time.time() - t0) * 1000), used_llm=used_llm, used_render=used_render,
    )
