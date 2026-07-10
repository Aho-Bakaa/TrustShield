"""Trust Score Engine — orchestrates pipeline → verdict.

Flow:
  1. Authenticity assessment (allowlist check)
  2. Detector run (LLM-first scoring)
  3. Fuse into a display-ready result

Key design decision: The LLM is the ONLY scoring authority. Fusion does NOT
override the detector's probability. It only assigns display levels (HIGH/MEDIUM/LOW)
and confidence based on signal richness.
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recommended_action(level: RiskLevel, channel: ChannelType, verified: bool) -> str:
    if verified and level == RiskLevel.LOW:
        return ("This appears to be a genuine official communication. "
                "Still confirm any sensitive action through the organisation's official app or website.")
    if level == RiskLevel.HIGH:
        return {
            ChannelType.EMAIL: "High risk. Do NOT click links or share OTP/password/KYC. Report to the impersonated entity and SEBI SCORES, then delete.",
            ChannelType.URL: "High risk. Do NOT enter credentials or payment details on this page. Report the domain and avoid it.",
            ChannelType.SOCIAL: "High risk. Do NOT act on this tip, join the linked group, or transfer funds. Report the post to the platform.",
            ChannelType.AUDIO: "High risk. Do NOT act on instructions in this call. Call back on the organisation's official published number to verify.",
        }.get(channel, "High risk. Do not act; verify through official channels and report.")
    if level == RiskLevel.MEDIUM:
        return ("Suspicious — do not act yet. Independently verify through the official website or app "
                "before sharing information, clicking, or transacting.")
    return "No strong threat signals detected. Stay cautious and verify sensitive actions independently."


def _level_for(risk: float, is_official: bool, official_conf: float) -> tuple[RiskLevel, str]:
    if is_official and official_conf >= 0.7 and risk < 0.3:
        return RiskLevel.LOW, "low"
    if risk >= 0.6:
        return RiskLevel.HIGH, "high"
    elif risk >= 0.3:
        return RiskLevel.MEDIUM, "medium"
    else:
        return RiskLevel.LOW, "low"


def _confidence(primary, auth) -> float:
    conf = 0.55
    if primary.used_llm:
        conf += 0.2
    if primary.used_render:
        conf += 0.1
    if len(primary.evidence) >= 5:
        conf += 0.1
    if auth.is_official_source or auth.official_confidence <= 0.1:
        conf += 0.05
    return max(0.4, min(conf, 0.98))


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

    primary = detector_mod.run(req, deep=True)
    trace.append(TraceStep(stage=f"deep:{det_name}",
                           detail=f"probability={primary.probability} "
                                  f"llm={primary.used_llm} render={primary.used_render}",
                           latency_ms=primary.latency_ms))

    if primary.fields.get("impersonated_entity") and not req.claimed_source:
        req.claimed_source = primary.fields["impersonated_entity"]

    risk = primary.probability
    level, severity = _level_for(risk, auth.is_official_source, auth.official_confidence)
    confidence = _confidence(primary, auth)

    evidence: list[Evidence] = list(primary.evidence)
    for s in auth.signals:
        evidence.append(Evidence(
            source="authenticity", label="Authenticity signal", detail=s,
            weight=(-0.15 if auth.is_official_source else 0.03), severity="info"))
    if crit >= 0.8 and level != RiskLevel.LOW:
        top = next((e.text for e in req.entities if e.criticality >= 0.8), "a critical entity")
        evidence.append(Evidence(
            source="fusion", label="High-criticality target",
            detail=f"Impersonation concerns a high-criticality entity ({top}).",
            weight=0.1, severity="high"))

    threat_label = _threat_label(primary, level, req.channel_type, auth)
    action = _recommended_action(level, req.channel_type, auth.is_official_source)

    summary = (
        f"{threat_label}. Risk {int(round(risk * 100))}/100 ({level.value}). "
        f"{primary.explanation}"
    )

    latency = int((datetime.now(timezone.utc) - t_start).total_seconds() * 1000)
    trace.append(TraceStep(stage="fusion",
                           detail=f"risk={int(round(risk * 100))} level={level.value} confidence={confidence:.2f}"))
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
        escalated=True,
        latency_ms=latency,
        created_at=_now(),
    )
