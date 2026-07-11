"""LLM-based message intent analysis.

Classifies what kind of communication this is — broker notification, phishing,
educational, etc. — and extracts claims to verify. No probability output;
the verdict LLM determines that independently.
"""
from __future__ import annotations

import re
from typing import Any

from .llm import reason_json
from .prompts import load as load_prompt

_ALARM_WORDS = re.compile(
    r"\b(scam|fraud|crackdown|banned|barred|suspended|arrested|seiz|raide?d|"
    r"guaranteed\s+return|insider\s+tip|100%\s+profit|double\s+your|"
    r"send\s+(otp|password|kyc|pin|secret)\b|account\s+suspended|"
    r"immediate(?:ly)?\s+(action|transfer|pay|verify)|"
    r"ceo\s+authorized|board\s+approved.*transfer)\b",
    re.I,
)
_SEBI_CLAIM = re.compile(r"\b(sebi|rbi|nse|bse|securities\s+exchange)\b", re.I)


def _keyword_signal(text: str, entities: list[str] | None) -> dict:
    text_lower = text.lower()
    has_alarm = bool(_ALARM_WORDS.search(text_lower))
    has_sebi = bool(_SEBI_CLAIM.search(text_lower))
    has_entity = any((e or "").lower() in text_lower for e in (entities or []))

    if has_alarm and has_entity:
        return {"classification": "spam_or_rumor", "confidence": 0.65,
                "impersonation_target": None,
                "claims_to_verify": [text[:200]],
                "explanation": "Unverified claim involving known entity with alarm language."}
    if has_alarm:
        return {"classification": "spam_or_rumor", "confidence": 0.5,
                "impersonation_target": None,
                "claims_to_verify": [],
                "explanation": "Contains alarm language but no clear entity match."}
    if has_sebi or has_entity:
        return {"classification": "uncertain", "confidence": 0.3,
                "impersonation_target": None,
                "claims_to_verify": [text[:200]],
                "explanation": "Mentions regulatory entity — claims need verification."}
    return {"classification": "uncertain", "confidence": 0.1,
            "impersonation_target": None, "claims_to_verify": [],
            "explanation": "Insufficient signals for classification."}


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
        return _keyword_signal(text, entities)

    data, used = reason_json(load_prompt("intent.txt"), user, _neutral)
    if not used:
        return _neutral()
    return data
