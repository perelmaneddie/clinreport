from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class VariantRecordModel(BaseModel):
    variant_id: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gene: str | None = None
    consequence: str | None = None
    clinvar: str | None = None
    gt: str | None = None
    dp: int | None = None
    gq: int | None = None
    af: float | None = None
    vaf: float | None = None
    qual: float | None = None
    filter: str | None = None


class TechnicalEvidence(BaseModel):
    dp: int | None = None
    ad_ref: int | None = None
    ad_alt: int | None = None
    vaf: float | None = None
    gq: int | None = None
    qual: float | None = None
    strand_balance: float | None = None
    mapping_quality: float | None = None
    base_quality: float | None = None
    in_low_complexity_region: bool = False
    duplicate_rate: float | None = None


class AuthenticityAssessment(BaseModel):
    variant_id: str
    authenticity_score: float
    confidence: float
    label: Literal["likely_real", "uncertain", "likely_artifact"]
    artifact_tags: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class ClinicalEvidenceItem(BaseModel):
    code: str
    strength: Literal["supporting", "moderate", "strong", "very_strong"]
    reason: str


class EvidenceMap(BaseModel):
    variant_id: str
    supports: list[ClinicalEvidenceItem] = Field(default_factory=list)
    contradicts: list[ClinicalEvidenceItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    state: Literal[
        "insufficient_evidence", "supports_benign", "supports_pathogenic", "conflicting_evidence"
    ] = "insufficient_evidence"
    rules_version: str = "v1"


class ReviewPacket(BaseModel):
    variant_id: str
    summary: str
    technical_summary: str
    evidence_summary: str
    conflicts: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    draft_rationale: str
    llm_model: str
    grounding_hash: str


class ReviewerDecision(BaseModel):
    case_id: str
    variant_id: str
    reviewer: str
    decision: Literal[
        "approve", "reject", "escalate", "request_more_evidence", "mark_orthogonal_confirmation", "defer"
    ]
    comment: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    override: bool = False
    escalation_reason: str | None = None


class AuditEvent(BaseModel):
    event_type: str
    case_id: str
    variant_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict = Field(default_factory=dict)
