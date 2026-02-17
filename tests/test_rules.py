from clinreport.vcf.io import VariantRecord
from clinreport.vcf.rules import low_confidence


def test_low_confidence_flags_dp():
    v = VariantRecord("chr1", 100, "A", "G", None, 50.0, "PASS", {}, "S", "0/1", 5, 30, 10, 5)
    lc = low_confidence(v)
    assert lc.is_low_conf
    assert any("DP<" in r for r in lc.reasons)
