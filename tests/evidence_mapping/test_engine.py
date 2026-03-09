from clinreport.core.models import AuthenticityAssessment, VariantRecordModel
from clinreport.evidence_mapping.engine import EvidenceMappingEngine


def _auth(label: str) -> AuthenticityAssessment:
    return AuthenticityAssessment(
        variant_id="chr1-100-A-G",
        authenticity_score=0.4,
        confidence=0.7,
        label=label,
        artifact_tags=[],
        reason_codes=[],
    )


def test_low_frequency_rule_triggers_support():
    engine = EvidenceMappingEngine(max_population_af=0.01)
    v = VariantRecordModel(variant_id="chr1-100-A-G", chrom="chr1", pos=100, ref="A", alt="G", af=0.001)
    m = engine.map(v, annotations={}, authenticity=_auth("likely_real"))
    assert any(x.code == "LOW_FREQ" for x in m.supports)


def test_conflicting_evidence_handled():
    engine = EvidenceMappingEngine(max_population_af=0.01)
    v = VariantRecordModel(
        variant_id="chr1-100-A-G",
        chrom="chr1",
        pos=100,
        ref="A",
        alt="G",
        af=0.02,
        clinvar="Pathogenic",
    )
    m = engine.map(v, annotations={}, authenticity=_auth("likely_real"))
    assert m.state == "conflicting_evidence"


def test_missing_evidence_detected_and_repeatable():
    engine = EvidenceMappingEngine()
    v = VariantRecordModel(variant_id="chr1-100-A-G", chrom="chr1", pos=100, ref="A", alt="G")
    m1 = engine.map(v, annotations={}, authenticity=_auth("uncertain"))
    m2 = engine.map(v, annotations={}, authenticity=_auth("uncertain"))
    assert m1.model_dump() == m2.model_dump()
    assert "population_frequency" in m1.missing
