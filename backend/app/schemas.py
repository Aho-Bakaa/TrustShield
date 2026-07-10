"""Shared data contracts for the TrustShield trust pipeline."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    EMAIL = "email"
    URL = "url"
    AUDIO = "audio"
    SOCIAL = "social"
    QUERY = "query"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"        # green  — verified / low risk
    MEDIUM = "medium"  # amber  — suspicious / review
    HIGH = "high"      # red    — high risk / likely fake


class Entity(BaseModel):
    text: str
    type: str  # regulator | exchange | broker | company | executive | scheme
    criticality: float = 0.5  # 0..1 — impersonating this entity raises severity


class LinkInfo(BaseModel):
    raw: str
    domain: str = ""
    registered_domain: str = ""
    suspicious: bool = False
    reasons: list[str] = Field(default_factory=list)
    allowlisted: bool = False


class Evidence(BaseModel):
    """A single interpretable signal that contributed to the verdict."""
    source: str                     # detector / engine that produced it
    label: str                      # short human label
    detail: str                     # explanation
    weight: float = 0.0             # signed contribution to risk (-1..1)
    severity: str = "info"          # info | low | medium | high


class DetectorResult(BaseModel):
    name: str
    channel: ChannelType
    probability: float = 0.0        # 0..1 threat probability for this modality
    label: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)  # modality-specific outputs
    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str = ""
    latency_ms: int = 0
    used_llm: bool = False
    used_render: bool = False


class AuthenticityResult(BaseModel):
    is_official_source: bool = False
    official_confidence: float = 0.0        # 0..1
    matched_entity: Optional[str] = None
    provenance_available: bool = False
    signals: list[str] = Field(default_factory=list)
    explanation: str = ""


class TraceStep(BaseModel):
    stage: str
    detail: str
    latency_ms: int = 0


class AnalysisRequest(BaseModel):
    """Normalized analysis request produced by the intake layer."""
    channel_type: ChannelType
    raw_input: str = ""
    claimed_source: Optional[str] = None
    links: list[LinkInfo] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)  # stored file paths
    audio_path: Optional[str] = None
    timestamp: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    id: str
    channel_type: ChannelType
    risk_score: int                 # 0..100
    risk_level: RiskLevel
    threat_label: str               # e.g. "Phishing impersonation"
    confidence: float               # 0..1
    severity: str                   # low | medium | high
    recommended_action: str
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    detectors: list[DetectorResult] = Field(default_factory=list)
    authenticity: AuthenticityResult = Field(default_factory=AuthenticityResult)
    entities: list[Entity] = Field(default_factory=list)
    links: list[LinkInfo] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    escalated: bool = False
    latency_ms: int = 0
    created_at: str = ""



class AnalyzeTextRequest(BaseModel):
    raw_input: str = Field(..., description="Email body, message, URL, or social post text/URL")
    channel_hint: Optional[ChannelType] = None
    claimed_source: Optional[str] = None
