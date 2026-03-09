import json
from pathlib import Path

from typer.testing import CliRunner

from clinreport.cli import app


runner = CliRunner()


def test_end_to_end_packet_signoff_export(tmp_path: Path):
    out = tmp_path / "out"
    report = out / "report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "important_variants": [
            {
                "gene": "PAH",
                "chrom": "chr12",
                "pos": 102840474,
                "ref": "T",
                "alt": "C",
                "gt": "1/1",
                "clinvar": "Pathogenic",
            }
        ]
    }
    report.write_text(json.dumps(payload), encoding="utf-8")

    packet_json = out / "review" / "packet.json"
    packet_md = out / "review" / "packet.md"

    r1 = runner.invoke(
        app,
        [
            "review-packet",
            "--case-id",
            "caseX",
            "--report-json",
            str(report),
            "--out-json",
            str(packet_json),
            "--out-md",
            str(packet_md),
        ],
    )
    assert r1.exit_code == 0

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    variant_id = packet["variant"]["variant_id"]

    final_json = out / "review" / "final.json"
    r_blocked = runner.invoke(
        app,
        [
            "final-export",
            "--case-id",
            "caseX",
            "--report-json",
            str(report),
            "--packet-json",
            str(packet_json),
            "--out-json",
            str(final_json),
        ],
    )
    assert r_blocked.exit_code != 0

    r2 = runner.invoke(
        app,
        [
            "signoff",
            "--case-id",
            "caseX",
            "--variant-id",
            variant_id,
            "--reviewer",
            "user@example.com",
            "--decision",
            "approve",
            "--out-dir",
            str(out / "review"),
        ],
    )
    assert r2.exit_code == 0

    r3 = runner.invoke(
        app,
        [
            "final-export",
            "--case-id",
            "caseX",
            "--report-json",
            str(report),
            "--packet-json",
            str(packet_json),
            "--decisions-json",
            str(out / "review" / "signoff_decisions.json"),
            "--out-json",
            str(final_json),
        ],
    )
    assert r3.exit_code == 0
    assert final_json.exists()
