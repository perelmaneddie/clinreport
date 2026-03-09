from clinreport.core.models import TechnicalEvidence, VariantRecordModel
from clinreport.technical_review.authenticity_engine import TechnicalAuthenticityEngine


def _v() -> VariantRecordModel:
    return VariantRecordModel(
        variant_id="chr1-100-A-G",
        chrom="chr1",
        pos=100,
        ref="A",
        alt="G",
        filter="PASS",
    )


def test_high_confidence_clean_snv():
    engine = TechnicalAuthenticityEngine()
    out = engine.assess(_v(), TechnicalEvidence(dp=40, gq=99, vaf=0.48))
    assert out.label == "likely_real"


def test_artifact_prone_low_vaf_case():
    engine = TechnicalAuthenticityEngine()
    out = engine.assess(_v(), TechnicalEvidence(dp=8, gq=10, vaf=0.02, in_low_complexity_region=True))
    assert out.label == "likely_artifact"
    assert "low_complexity_region" in out.artifact_tags


def test_missing_metrics_case_uncertain_or_real_but_valid():
    engine = TechnicalAuthenticityEngine()
    out = engine.assess(_v(), TechnicalEvidence())
    assert 0.0 <= out.authenticity_score <= 1.0
