from pathlib import Path

from clinreport.igv.batch import IgvBatchParams, write_igv_batch
from clinreport.vcf.io import VariantRecord


def test_igv_batch_contains_snapshot_commands(tmp_path: Path):
    v = VariantRecord("chr1", 100, "A", "G", None, 50.0, "PASS", {}, "S", "0/1", 20, 30, 10, 10)
    params = IgvBatchParams(genome="hg38", bam_or_cram="sample.bam", snapshot_dir=tmp_path / "snaps")
    bat = tmp_path / "test.igv"
    write_igv_batch(bat, [v], params, sample_name="SAMPLE")
    txt = bat.read_text(encoding="utf-8")
    assert "snapshotDirectory" in txt
    assert "snapshot" in txt
    assert "goto" in txt
