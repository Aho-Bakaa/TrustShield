"""LLM-based message intent analysis.

Replaces regex heuristics entirely. The LLM reads the message, classifies
intent, identifies impersonation targets, and extracts factual claims to verify.

Runs on every submission — cheap (~700ms on Groq), always available.
"""
from __future__ import annotations

from typing import Any

from .llm import reason_json
from .prompts import load as load_prompt


def analyze_message(text: str, entities: list[str] | None = None,
                    link_allowlisted: bool = False, link_suspicious: bool = False,
                    link_reasons: list[str] | None = None) -> dict[str, Any]:
    user = f"MESSAGE:\n{text[:2000]}\n\n"
    if entities:
        user += f"KNOWN ENTITIES MENTIONED: {entities}\n"
    if link_suspicious:
        user += "NOTE: This message contains a suspicious link.\n"
    if link_allowlisted:
        user += "NOTE: This message links to an official, allowlisted domain.\n"

    def _neutral():
        prob = 0.25
        if link_allowlisted and not link_suspicious:
            prob = 0.05
        elif link_suspicious and link_reasons:
            prob = min(1.0, 0.5 + 0.08 * len(link_reasons))
        elif link_suspicious:
            prob = 0.55
        return {
            "intent": "uncertain",
            "phishing_probability": prob,
            "impersonation_target": None,
            "credential_request_detected": False,
            "urgency_detected": False,
            "authority_claim_detected": False,
            "financial_lure_detected": False,
            "claims_to_verify": [],
            "explanation": "LLM unavailable; fallback assessment based on link reputation.",
        }

    data, used = reason_json(load_prompt("intent.txt"), user, _neutral)
    if not used:
        return _neutral()
    return data
