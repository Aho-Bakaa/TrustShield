"""Trust Score Engine — orchestrates triage → deep analysis → fusion.

Flow:
  1. Authenticity assessment (is this a verifiable official source?).
  2. Cheap triage run of the channel's detector (no network/LLM).
  3. Escalate to deep analysis (render + LLM) if triage is non-trivial OR a
     high-criticality entity (SEBI/exchange) is impersonated.
  4. Fuse detector probability + authenticity + entity criticality + provenance
     into a single 0-100 risk score, level, confidence, and recommended action.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .config import get_settings
from .detectors import authenticity as authenticity_engine
from .detectors import phishing, social, voice
from .log import get_logger
from .preprocessing.entities import max_criticality
from .schemas import (
    AnalysisRequest,
    AnalysisResult,
    ChannelType,
    Evidence,
    RiskLevel,
    TraceStep,
)

_log = get_logger("fusion")

_DETECTOR_FOR = {
    ChannelType.EMAIL: phishing,
    ChannelType.URL: phishing,
    ChannelType.SOCIAL: social,
    ChannelType.AUDIO: voice,
    ChannelType.UNKNOWN: phishing,
}

_ALWAYS_DEEP = {ChannelType.URL, ChannelType.SOCIAL, ChannelType.AUDIO}


def _escalation_decision(req: AnalysisRequest, triage, auth, crit, threshold):
    """Return (escalate: bool, reason: str)."""
    if auth.is_official_source and auth.official_confidence >= 0.7 and triage.probability < 0.3 and not req.links:
        return False, "verified official source, no links (no deep pass needed)"
    if req.channel_type in _ALWAYS_DEEP:
        return True, f"{req.channel_type.value} channel is always deep-analyzed"
    if req.links:
        return True, "message contains link(s) to inspect"
    if crit >= 0.8:
        return True, "impersonates a high-criticality entity"
    if triage.probability >= threshold:
        return True, f"triage {triage.probability:.2f} >= {threshold}"
    return False, "low triage, no links or critical entities"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recommended_action(level: RiskLevel, channel: ChannelType, verified: bool) -> str:
    if verified and level == RiskLevel.LOW:
        return ("Appears to be a genuine official communication (allowlisted source). "
                "Still confirm any sensitive action through the organisation's official app/website.")
    if level == RiskLevel.HIGH:
        return {
            ChannelType.EMAIL: "High risk. Do NOT click links or share OTP/password/KYC. Report to the impersonated entity and SEBI SCORES (scores.sebi.gov.in), then delete.",
            ChannelType.URL: "High risk. Do NOT enter credentials or payment details on this page. Report the domain and avoid it.",
            ChannelType.SOCIAL: "High risk. Do NOT act on this tip, join the linked group, or transfer funds. Report the post to the platform and to SEBI.",
            ChannelType.AUDIO: "High risk. Do NOT act on instructions in this call. Call back on the organisation's official published number to verify before doing anything.",
        }.get(channel, "High risk. Do not act; verify through official channels and report.")
    if level == RiskLevel.MEDIUM:
        return ("Suspicious — do not act yet. Independently verify through the official website/app "
                "or published helpline before sharing information, clicking, or transacting.")
    return "No strong threat signals detected. Stay cautious and verify sensitive actions independently."


def _fuse(primary, auth, crit: float) -> tuple[float, RiskLevel, str, float]:
    """Return (risk 0..1, level, severity, confidence)."""
    risk = primary.probability

    if auth.is_official_source and auth.official_confidence >= 0.8:
        risk = min(risk, 0.15)                      # verified official caps risk
    elif auth.official_confidence <= 0.1 and any("NOT verified" in s for s in auth.signals):
        risk = max(risk, 0.65)                      # claimed-official + off-domain mismatch

    if not auth.provenance_available and risk >= 0.4:
        risk = min(1.0, risk + 0.05)

    if risk >= 0.6 or (risk >= 0.4 and crit >= 0.8):
        level, severity = RiskLevel.HIGH, "high"
    elif risk >= 0.3 or (risk >= 0.22 and crit >= 0.8):
        level, severity = RiskLevel.MEDIUM, "medium"
    else:
        level, severity = RiskLevel.LOW, "low"

    if auth.is_official_source and auth.official_confidence >= 0.7:
        level, severity = RiskLevel.LOW, "low"

    conf = 0.55
    if primary.used_llm:
        conf += 0.15
    if primary.used_render:
        conf += 0.1
    if len(primary.evidence) >= 3:
        conf += 0.1
    if auth.is_official_source or auth.official_confidence <= 0.1:
        conf += 0.07
    conf = max(0.4, min(conf, 0.97))
    return risk, level, severity, conf


def _threat_label(primary, level: RiskLevel, channel: ChannelType, auth) -> str:
    if auth.is_official_source and level == RiskLevel.LOW:
        return f"Verified official communication - {auth.matched_entity}"
    imp = primary.fields.get("impersonated_entity") or primary.fields.get("impersonation_target")
    base = {
        ChannelType.EMAIL: "Phishing impersonation",
        ChannelType.URL: "Phishing / credential-capture page",
        ChannelType.SOCIAL: "Social-media market manipulation",
        ChannelType.AUDIO: "Suspected synthetic voice impersonation",
    }.get(channel, "Suspicious communication")
    if level == RiskLevel.LOW:
        return f"Low risk ({channel.value})"
    if imp and level != RiskLevel.LOW:
        return f"{base} - targeting {imp}"
    return base


def analyze(req: AnalysisRequest) -> AnalysisResult:
    settings = get_settings()
    trace: list[TraceStep] = []
    t_start = datetime.now(timezone.utc)
    aid = uuid.uuid4().hex[:12]
    tag = f"[{aid[:6]}]"

    detector_mod = _DETECTOR_FOR.get(req.channel_type, phishing)
    det_name = detector_mod.__name__.split(".")[-1]
    crit = max_criticality(req.entities)

    _log.info("%s channel=%s entities=%s links=%d preview=%r", tag, req.channel_type.value,
              [e.text for e in req.entities], len(req.links), (req.raw_input or req.audio_path or "")[:70])
    trace.append(TraceStep(stage="intake",
                           detail=f"Channel classified as '{req.channel_type.value}'; "
                                  f"{len(req.links)} link(s), {len(req.entities)} entity(ies)."))

    auth = authenticity_engine.assess(req)
    trace.append(TraceStep(stage="authenticity",
                           detail=f"official={auth.is_official_source} "
                                  f"confidence={auth.official_confidence}"))

    triage = detector_mod.run(req, deep=False)
    trace.append(TraceStep(stage=f"triage:{det_name}",
                           detail=f"preliminary probability={triage.probability}",
                           latency_ms=triage.latency_ms))

    escalate, reason = _escalation_decision(req, triage, auth, crit, settings.triage_escalation_threshold)
    _log.info("%s triage=%.2f -> %s (%s)", tag, triage.probability,
              "ESCALATE" if escalate else "triage-only", reason)

    if escalate:
        primary = detector_mod.run(req, deep=True)
        trace.append(TraceStep(stage=f"deep:{det_name}",
                               detail=f"probability={primary.probability} "
                                      f"llm={primary.used_llm} render={primary.used_render} ({reason})",
                               latency_ms=primary.latency_ms))
    else:
        primary = triage
        trace.append(TraceStep(stage="deep", detail=f"skipped — {reason}"))

    risk, level, severity, confidence = _fuse(primary, auth, crit)

    evidence: list[Evidence] = list(primary.evidence)
    for s in auth.signals:
        evidence.append(Evidence(
            source="authenticity", label="Authenticity signal", detail=s,
            weight=(-0.2 if auth.is_official_source else 0.05), severity="info"))
    if crit >= 0.8 and level != RiskLevel.LOW:
        top = next((e.text for e in req.entities if e.criticality >= 0.8), "a critical entity")
        evidence.append(Evidence(
            source="fusion", label="High-criticality target",
            detail=f"Impersonation concerns a high-criticality entity ({top}); severity raised.",
            weight=0.15, severity="high"))

    threat_label = _threat_label(primary, level, req.channel_type, auth)
    action = _recommended_action(level, req.channel_type, auth.is_official_source)

    summary = (
        f"{threat_label}. Risk {int(round(risk*100))}/100 ({level.value}). "
        f"{primary.explanation}"
    )

    latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
    trace.append(TraceStep(stage="fusion",
                           detail=f"risk={int(round(risk*100))} level={level.value} confidence={confidence}"))
    _log.info("%s VERDICT risk=%d %s %r llm=%s render=%s %dms", tag, int(round(risk * 100)),
              level.value, threat_label, primary.used_llm, primary.used_render, latency)

    return AnalysisResult(
        id=aid,
        channel_type=req.channel_type,
        risk_score=int(round(risk * 100)),
        risk_level=level,
        threat_label=threat_label,
        confidence=round(confidence, 3),
        severity=severity,
        recommended_action=action,
        summary=summary,
        evidence=evidence,
        detectors=[primary],
        authenticity=auth,
        entities=req.entities,
        links=req.links,
        trace=trace,
        escalated=escalate,
        latency_ms=latency,
        created_at=_now(),
    )
