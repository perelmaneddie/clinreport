from __future__ import annotations

from ..core.models import AuthenticityAssessment, EvidenceMap


def route_review_queue(authenticity: AuthenticityAssessment, evidence_map: EvidenceMap) -> str:
    if evidence_map.missing and any(m in evidence_map.missing for m in ("population_frequency", "consequence_annotation")):
        return "blocked_missing_data"
    if authenticity.label == "likely_artifact":
        return "light_review"
    if evidence_map.state == "conflicting_evidence":
        return "expert_review"
    if authenticity.label == "uncertain":
        return "needs_orthogonal_confirmation"
    if authenticity.label == "likely_real" and evidence_map.state in ("supports_pathogenic", "supports_benign"):
        return "auto_pass_to_light_review"
    return "light_review"
