"""LLM-based message intent analysis.

Classifies what kind of communication this is — broker notification, phishing,
educational, etc. — and extracts claims to verify. No probability output;
the verdict LLM determines that independently.
"""
from __future__ import annotations

from typing import Any

from .llm import reason_json
from .prompts import load as load_prompt


def analyze_message(text: str, entities: list[str] | None = None,
                    link_allowlisted: bool = False, link_suspicious: bool = False,
                    link_reasons: list[str] | None = None) -> dict[str, Any]:
    user = f"MESSAGE:\n{text[:3000]}\n\n"
    if entities:
        user += f"KNOWN ENTITIES MENTIONED: {entities}\n"
    if link_suspicious:
        user += "NOTE: This message contains a suspicious link.\n"
    if link_allowlisted:
        user += "NOTE: This message links to an official, allowlisted domain.\n"

    def _neutral():
        if link_allowlisted and not link_suspicious:
            return {"classification": "broker_notification", "confidence": 0.8,
                    "impersonation_target": None, "claims_to_verify": [],
                    "explanation": "Link resolves to verified official domain."}
        if link_suspicious and link_reasons:
            severity = min(1.0, 0.5 + 0.15 * len(link_reasons))
            return {"classification": "phishing_email", "confidence": severity,
                    "impersonation_target": entities[0] if entities else None,
                    "claims_to_verify": [],
                    "explanation": "Suspicious link with multiple risk signals."}
        return {"classification": "uncertain", "confidence": 0.1,
                "impersonation_target": None, "claims_to_verify": [],
                "explanation": "LLM unavailable."}

    data, used = reason_json(load_prompt("intent.txt"), user, _neutral)
    if not used:
        return _neutral()
    return data
