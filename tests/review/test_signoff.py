from pathlib import Path

from clinreport.core.models import ReviewerDecision
from clinreport.review.signoff import has_signoff, save_reviewer_decision


def test_signoff_persistence_and_lookup(tmp_path: Path):
    p = tmp_path / "signoff.json"
    save_reviewer_decision(
        p,
        ReviewerDecision(
            case_id="case1",
            variant_id="chr1-100-A-G",
            reviewer="user@example.com",
            decision="approve",
        ),
    )
    assert has_signoff(p, "case1", "chr1-100-A-G")
