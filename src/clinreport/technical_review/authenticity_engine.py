from __future__ import annotations

from dataclasses import dataclass

from ..core.models import AuthenticityAssessment, TechnicalEvidence, VariantRecordModel


@dataclass
class TechnicalAuthenticityEngine:
    min_dp: int = 10
    min_gq: int = 20

    def assess(self, variant: VariantRecordModel, context: TechnicalEvidence) -> AuthenticityAssessment:
        score = 0.5
        reasons: list[str] = []
        tags: list[str] = []

        if context.dp is not None:
            if context.dp >= self.min_dp:
                score += 0.15
                reasons.append("good_depth")
            else:
                score -= 0.2
                reasons.append("low_depth")
                tags.append("weak_support")

        if context.gq is not None:
            if context.gq >= self.min_gq:
                score += 0.1
                reasons.append("good_genotype_quality")
            else:
                score -= 0.15
                reasons.append("low_genotype_quality")
                tags.append("weak_support")

        vaf = context.vaf
        if vaf is None and context.ad_ref is not None and context.ad_alt is not None:
            denom = context.ad_ref + context.ad_alt
            if denom > 0:
                vaf = context.ad_alt / denom

        if vaf is not None:
            if vaf < 0.05:
                score -= 0.2
                reasons.append("very_low_vaf")
                tags.append("low_vaf")
            elif vaf < 0.2:
                score -= 0.05
                reasons.append("low_vaf")
                tags.append("low_vaf")
            else:
                score += 0.05
                reasons.append("adequate_vaf")

        if context.in_low_complexity_region:
            score -= 0.15
            reasons.append("low_complexity_region")
            tags.append("low_complexity_region")

        if variant.filter and variant.filter not in ("PASS", ".", ""):
            score -= 0.2
            reasons.append("failed_filter")
            tags.append("weak_support")

        score = max(0.0, min(1.0, score))

        if score >= 0.7:
            label = "likely_real"
        elif score <= 0.35:
            label = "likely_artifact"
        else:
            label = "uncertain"

        confidence = 0.5 + abs(score - 0.5)
        confidence = max(0.0, min(1.0, confidence))

        return AuthenticityAssessment(
            variant_id=variant.variant_id,
            authenticity_score=round(score, 3),
            confidence=round(confidence, 3),
            label=label,
            artifact_tags=sorted(set(tags)),
            reason_codes=sorted(set(reasons)),
        )
