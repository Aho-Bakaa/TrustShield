"""Manipulation / social-engineering phrase heuristics.

Shared by the phishing and social detectors as a cheap, explainable first pass.
Each category returns the phrases that fired so the UI can show *why*.
"""
from __future__ import annotations

import re

_CATEGORIES: dict[str, list[str]] = {
    "urgency": [
        r"\burgent\b", r"\bimmediately\b", r"\bwithin \d+ ?(hours?|minutes?|hrs?)\b",
        r"\bact now\b", r"\blast chance\b", r"\bexpir(e|es|ing|ed)\b", r"\bdeadline\b",
        r"\btoday only\b", r"\bfinal (notice|warning|reminder)\b",
    ],
    "threat_penalty": [
        r"\bsuspend(ed|ing)?\b", r"\bblock(ed|ing)?\b", r"\bfrozen?\b", r"\bpenalt", r"\blegal action\b",
        r"\baccount (will be )?(closed|deactivated|terminated)\b", r"\bfailure to\b",
    ],
    "credential_request": [
        r"\botp\b", r"\bpassword\b", r"\bpin\b", r"\bkyc\b", r"\bverify your account\b",
        r"\bupdate your (bank|account|kyc)\b", r"\bshare (your )?(otp|pin|password)\b",
        r"\bre-?activate\b", r"\bre-?verify\b",
    ],
    "financial_lure": [
        r"\bguaranteed (returns?|profit)\b", r"\b\d{2,}\s?%\s?(returns?|profit|monthly|daily)\b",
        r"\bmultibagger\b", r"\bsure ?shot\b", r"\brisk[- ]free\b", r"\bdouble your (money|investment)\b",
        r"\binsider (tip|info|information)\b", r"\bpre[- ]?ipo\b", r"\ballotment\b",
        r"\blimited (seats|slots)\b", r"\bjoin (our )?(telegram|whatsapp) (group|channel)\b",
    ],
    "authority_claim": [
        r"\bsebi[- ]?(registered|approved|certified)\b", r"\bofficial (notice|circular|advisory)\b",
        r"\bregulator\b", r"\bcompliance (team|department)\b", r"\bgovernment (approved|scheme)\b",
    ],
    "payment_request": [
        r"\bpay (a )?(fee|charge|deposit|margin)\b", r"\bupi\b", r"\bwallet\b", r"\btransfer (funds|money)\b",
        r"\bprocessing fee\b", r"\brefund\b", r"\bredeem\b",
    ],
}

_WEIGHTS = {
    "urgency": 0.12,
    "threat_penalty": 0.18,
    "credential_request": 0.22,
    "financial_lure": 0.2,
    "authority_claim": 0.14,
    "payment_request": 0.18,
}


def scan(text: str) -> dict:
    """Return fired categories, matched phrases, and a heuristic 0..1 score."""
    text = text or ""
    hits: dict[str, list[str]] = {}
    for cat, patterns in _CATEGORIES.items():
        matched: list[str] = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.I):
                phrase = m.group(0).strip()
                if phrase and phrase.lower() not in [x.lower() for x in matched]:
                    matched.append(phrase)
        if matched:
            hits[cat] = matched

    score = 0.0
    for cat in hits:
        score += _WEIGHTS.get(cat, 0.1)
    score = min(score, 1.0)

    return {
        "categories": hits,
        "score": round(score, 3),
        "fired": list(hits.keys()),
    }


CATEGORY_LABELS = {
    "urgency": "Urgency / time pressure",
    "threat_penalty": "Threat of penalty / account action",
    "credential_request": "Requests credentials (OTP/PIN/KYC)",
    "financial_lure": "Unrealistic financial lure",
    "authority_claim": "Claims official authority",
    "payment_request": "Requests payment / fund transfer",
}
