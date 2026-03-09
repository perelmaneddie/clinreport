from __future__ import annotations

from dataclasses import dataclass

from ..core.models import AuthenticityAssessment, ClinicalEvidenceItem, EvidenceMap, VariantRecordModel


@dataclass
class EvidenceMappingEngine:
    max_population_af: float = 0.01
    rules_version: str = "v1"

    def map(self, variant: VariantRecordModel, annotations: dict, authenticity: AuthenticityAssessment) -> EvidenceMap:
        supports: list[ClinicalEvidenceItem] = []
        contradicts: list[ClinicalEvidenceItem] = []
        missing: list[str] = []

        pop_af = annotations.get("gnomad_af", variant.af)
        if pop_af is None:
            missing.append("population_frequency")
        elif pop_af <= self.max_population_af:
            supports.append(
                ClinicalEvidenceItem(
                    code="LOW_FREQ",
                    strength="moderate",
                    reason=f"Population AF {pop_af:.5f} <= {self.max_population_af}",
                )
            )
        else:
            contradicts.append(
                ClinicalEvidenceItem(
                    code="HIGH_FREQ",
                    strength="strong",
                    reason=f"Population AF {pop_af:.5f} > {self.max_population_af}",
                )
            )

        clnsig = (variant.clinvar or annotations.get("clinvar") or "").replace(" ", "_")
        if not clnsig:
            missing.append("clinvar_assertion")
        elif "Pathogenic" in clnsig:
            supports.append(
                ClinicalEvidenceItem(
                    code="CLINVAR_PATH",
                    strength="moderate",
                    reason=f"ClinVar assertion: {clnsig}",
                )
            )
        elif "Benign" in clnsig:
            contradicts.append(
                ClinicalEvidenceItem(
                    code="CLINVAR_BENIGN",
                    strength="moderate",
                    reason=f"ClinVar assertion: {clnsig}",
                )
            )

        consequence = (variant.consequence or annotations.get("consequence") or "").lower()
        if not consequence:
            missing.append("consequence_annotation")
        elif any(k in consequence for k in ("stop_gained", "frameshift", "splice_acceptor", "splice_donor")):
            supports.append(
                ClinicalEvidenceItem(
                    code="HIGH_IMPACT_CONSEQUENCE",
                    strength="supporting",
                    reason=f"Consequence {consequence} suggests high impact",
                )
            )

        if authenticity.label == "likely_artifact":
            contradicts.append(
                ClinicalEvidenceItem(
                    code="LOW_TECH_CONF",
                    strength="supporting",
                    reason="Technical authenticity assessment indicates likely artifact",
                )
            )
        elif authenticity.label == "uncertain":
            missing.append("orthogonal_confirmation")

        if supports and contradicts:
            state = "conflicting_evidence"
        elif supports:
            state = "supports_pathogenic"
        elif contradicts:
            state = "supports_benign"
        else:
            state = "insufficient_evidence"

        return EvidenceMap(
            variant_id=variant.variant_id,
            supports=supports,
            contradicts=contradicts,
            missing=sorted(set(missing)),
            state=state,
            rules_version=self.rules_version,
        )
