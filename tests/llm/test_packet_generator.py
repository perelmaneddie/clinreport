from clinreport.core.models import AuthenticityAssessment, EvidenceMap, VariantRecordModel
from clinreport.llm.packet_generator import ReviewPacketGenerator


def test_packet_contains_required_sections_and_human_review_language():
    gen = ReviewPacketGenerator()
    packet = gen.generate(
        variant=VariantRecordModel(
            variant_id="chr1-100-A-G", chrom="chr1", pos=100, ref="A", alt="G", clinvar="Pathogenic"
        ),
        authenticity=AuthenticityAssessment(
            variant_id="chr1-100-A-G",
            authenticity_score=0.8,
            confidence=0.8,
            label="likely_real",
            artifact_tags=[],
            reason_codes=["good_depth"],
        ),
        evidence_map=EvidenceMap(variant_id="chr1-100-A-G", state="supports_pathogenic"),
        use_llm=False,
    )
    assert packet.summary
    assert packet.technical_summary
    assert packet.evidence_summary
    assert "human review" in packet.draft_rationale.lower() or any(
        "human review" in x.lower() for x in packet.recommended_actions
    )
