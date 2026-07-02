"""Authenticity / verification layer.

The complement to threat detection: given a communication, how confident are we
that it is a genuine official source? Uses the domain allowlist as a trust
registry, checks claimed-source vs. actual-destination consistency, and includes
provenance placeholders (DKIM-style signature / C2PA media provenance).
"""
from __future__ import annotations

import re

from ..registry import official_domains
from ..schemas import AnalysisRequest, AuthenticityResult


def _mentions_official(req: AnalysisRequest) -> str | None:
    for e in req.entities:
        if e.criticality >= 0.8:
            return e.text
    src = (req.claimed_source or "").lower()
    for d, meta in official_domains().items():
        if meta["entity"].lower() in src or d.split(".")[0] in src:
            return meta["entity"]
    return None


def assess(req: AnalysisRequest) -> AuthenticityResult:
    signals: list[str] = []
    allowlisted = [l for l in req.links if l.allowlisted]
    suspicious = [l for l in req.links if l.suspicious and not l.allowlisted]
    claimed_official = _mentions_official(req)

    confidence = 0.0
    is_official = False
    matched_entity = None
    provenance = False

    if allowlisted and not suspicious:
        matched_entity = official_domains().get(
            allowlisted[0].registered_domain,
            official_domains().get(allowlisted[0].domain, {}),
        ).get("entity", allowlisted[0].registered_domain)
        is_official = True
        confidence = 0.9
        signals.append(f"All links resolve to official allowlisted domain(s): {matched_entity}")
    elif allowlisted and suspicious:
        confidence = 0.35
        signals.append("Message mixes official and non-official links — treat with caution")
    elif claimed_official and suspicious:
        confidence = 0.05
        signals.append(
            f"Claims to be from {claimed_official} but links to non-official domain "
            f"{suspicious[0].registered_domain} — authenticity NOT verified"
        )
    elif claimed_official and not req.links:
        confidence = 0.3
        signals.append(f"References {claimed_official} but has no verifiable official link")
    else:
        confidence = 0.2
        signals.append("No official allowlisted source found to verify against")

    text = req.raw_input or ""
    if re.search(r"dkim=pass|spf=pass|signed by", text, re.I):
        provenance = True
        confidence = min(1.0, confidence + 0.05)
        signals.append("Message headers indicate a passing DKIM/SPF signature (provenance present)")
    else:
        signals.append("No cryptographic provenance (DKIM/SPF/C2PA) available to attest the source")

    explanation = (
        f"Verified official source ({matched_entity}) with high confidence."
        if is_official
        else "Could not verify this as a genuine official communication."
    )

    return AuthenticityResult(
        is_official_source=is_official,
        official_confidence=round(confidence, 3),
        matched_entity=matched_entity,
        provenance_available=provenance,
        signals=signals,
        explanation=explanation,
    )
