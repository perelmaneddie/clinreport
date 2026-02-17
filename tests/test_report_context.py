from pathlib import Path

from clinreport.report.render import render_html


def test_render_html(tmp_path: Path):
    template_dir = Path(__file__).parent.parent / "src" / "clinreport" / "report" / "templates"
    out_html = tmp_path / "r.html"
    context = {
        "sample": "SAMPLE",
        "assembly": "GRCh38",
        "generated_at": "2026-01-01T00:00:00Z",
        "provenance_json": "{}",
        "qc": None,
        "important_variants": [],
        "low_confidence": [],
        "css": "",
    }
    render_html(template_dir, context, out_html)
    assert out_html.exists()
    assert "Clinical Variant Report" in out_html.read_text(encoding="utf-8")
