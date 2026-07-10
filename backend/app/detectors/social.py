"""Social-media manipulation detector — LLM-first scoring.

Same pattern as phishing.py: intent LLM → Playwright → vision → search → verdict.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any

from ..intent import analyze_message
from ..llm import analyze_screenshot, reason_json
from ..prompts import load as load_prompt
from ..render import render
from ..search import verify_batch
from ..schemas import AnalysisRequest, ChannelType, DetectorResult, Evidence


def run(req: AnalysisRequest, deep: bool) -> DetectorResult:
    t0 = time.time()
    evidence: list[Evidence] = []
    used_llm = False
    used_render = False

    entities_list = [e.text for e in req.entities]

    intent = analyze_message(req.raw_input, entities_list)
    used_llm = True

    classific = intent.get("classification", "uncertain")
    evidence.append(Evidence(
        source="intent", label="Message classification",
        detail=f"Classified as: {classific}. {intent.get('explanation', '')}",
        weight=0.0, severity="info"))

    prob = 0.10
    fields: dict[str, Any] = {
        "classification": classific,
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

            claims_raw = intent.get("claims_to_verify", [])
            if claims_raw and isinstance(claims_raw[0], str):
                claims = [{"text": c, "type": "llm_claim", "verified": False, "sources": [], "contradicted": False} for c in claims_raw] if claims_raw else []
            elif claims_raw:
                claims = claims_raw
            else:
                claims = extract_claims(req.raw_input)

            if claims:
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                search_future = pool.submit(verify_claims_sync, claims)
                try:
                    claim_results = search_future.result(timeout=6)
                except Exception:
                    claim_results = claims
                pool.shutdown(wait=False)
            else:
                claim_results = []

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

            import json
            rendered_data = {
                "final_url": rendered.get("final_url"),
                "title": rendered.get("title"),
                "og_site_name": rendered.get("og_site_name"),
                "captures_sensitive": rendered.get("captures_sensitive"),
                "cross_domain": rendered.get("cross_domain_redirect"),
                "external_domains": rendered.get("external_domains", []),
                "text_excerpt": (rendered.get("text_excerpt") or "")[:800],
            } if rendered.get("rendered") else "No rendered page."

            forensic = rendered.get("forensic", {})
            forensic_data = {
                "is_https": forensic.get("is_https"),
                "final_domain": forensic.get("final_domain"),
                "iframe_count": forensic.get("iframe_count"),
                "cross_domain_link_count": forensic.get("cross_domain_link_count"),
                "resource_count": forensic.get("resource_count"),
                "console_errors": forensic.get("console_error_count", 0),
                "meta_refresh": forensic.get("meta_refresh_tag"),
                "whois": {
                    "registrar": forensic.get("whois", {}).get("registrar"),
                    "creation_date": forensic.get("whois", {}).get("creation_date"),
                } if forensic.get("whois") else {},
            } if forensic else "No forensic data."

            screenshot_data = {
                "page_type": screenshot_analysis.get("page_type"),
                "imitates_brand": screenshot_analysis.get("imitates_brand"),
                "looks_deceptive": screenshot_analysis.get("looks_deceptive"),
                "notes": screenshot_analysis.get("notes"),
            } if screenshot_analysis else "No screenshot."

            intent_data = {
                "classification": classific,
                "confidence": intent.get("confidence", 0.0),
                "explanation": intent.get("explanation"),
            }

            user = (
                f"## POST TEXT\n{req.raw_input[:2000]}\n\n"
                f"## INTENT ANALYSIS\n{json.dumps(intent_data, indent=2, default=str)}\n\n"
                f"## RENDERED PAGE\n{json.dumps(rendered_data, indent=2, default=str)}\n\n"
                f"## FORENSIC DATA\n{json.dumps(forensic_data, indent=2, default=str)}\n\n"
                f"## SCREENSHOT\n{json.dumps(screenshot_data, indent=2, default=str)}\n"
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
