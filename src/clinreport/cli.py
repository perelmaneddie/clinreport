from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import typer

from .exceptions import InputValidationError
from .igv.batch import IgvBatchParams, write_igv_batch
from .igv.runner import run_igv_batch
from .llm.openai_triage import triage_snapshot
from .logging_utils import setup_logging
from .provenance import collect_versions, write_provenance
from .qc.fastq_qc import run_fastp
from .report.render import html_to_pdf, render_html
from .vcf.clinvar import ClinVarStreamMatcher
from .vcf.io import iter_variants
from .vcf.rules import low_confidence

app = typer.Typer(add_completion=False)
log = logging.getLogger(__name__)


def _read_css(template_dir: Path) -> str:
    css_path = template_dir / "style.css"
    return css_path.read_text(encoding="utf-8") if css_path.exists() else ""


def _is_clinvar_pathogenic(clnsig: str) -> bool:
    if not clnsig:
        return False
    normalized = clnsig.replace(" ", "_")
    labels = [p for p in re.split(r"[|,;/]+", normalized) if p]
    accepted = {"Pathogenic", "Likely_pathogenic", "Pathogenic/Likely_pathogenic"}
    if any(lbl in accepted for lbl in labels):
        return True
    if "Pathogenic/Likely_pathogenic" in normalized:
        return True
    return False


@app.callback()
def main(verbosity: int = typer.Option(0, "-v", count=True, help="Increase verbosity")):
    setup_logging(verbosity)


@app.command()
def run(
    vcf: Path = typer.Option(..., exists=True, help="Input VCF (prefer bgzipped + indexed)"),
    assembly: str = typer.Option("GRCh38", help="Reference build label for report"),
    out_dir: Path = typer.Option(Path("out"), help="Output directory"),
    fastq1: Path | None = typer.Option(None, exists=True, help="FASTQ R1 (optional QC)"),
    fastq2: Path | None = typer.Option(None, exists=True, help="FASTQ R2 (optional QC)"),
    clinvar_vcf: Path | None = typer.Option(
        None,
        exists=True,
        help="Optional ClinVar VCF.gz for annotation (e.g. clinvar.vcf.gz GRCh38)",
    ),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    versions = collect_versions()
    prov_dir = out_dir / "metadata"
    write_provenance(prov_dir, versions, extra={"assembly": assembly, "vcf": str(vcf)})

    qc = None
    if fastq1:
        qc = run_fastp(str(fastq1), str(fastq2) if fastq2 else None, out_dir / "qc")

    important = []
    lowc = []
    clinvar_matcher = ClinVarStreamMatcher(str(clinvar_vcf)) if clinvar_vcf else None

    for v in iter_variants(str(vcf)):
        lc = low_confidence(v)
        if lc.is_low_conf:
            lowc.append(
                {
                    "chrom": v.chrom,
                    "pos": v.pos,
                    "ref": v.ref,
                    "alt": v.alt,
                    "gt": v.gt,
                    "dp": v.dp,
                    "gq": v.gq,
                    "reasons": lc.reasons,
                    "snapshot": None,
                }
            )

        clinvar = str(v.info.get("CLNSIG", "")).strip()
        gene = str(v.info.get("GENE", "")).strip()
        if clinvar_matcher and (not clinvar or not gene):
            hit = clinvar_matcher.match(v)
            if hit:
                if not clinvar:
                    clinvar = hit.clnsig
                if not gene:
                    gene = hit.gene

        if _is_clinvar_pathogenic(clinvar):
            important.append(
                {
                    "gene": gene,
                    "chrom": v.chrom,
                    "pos": v.pos,
                    "ref": v.ref,
                    "alt": v.alt,
                    "gt": v.gt,
                    "dp": v.dp,
                    "gq": v.gq,
                    "clinvar": clinvar,
                    "notes": "",
                }
            )

    template_dir = Path(__file__).parent / "report" / "templates"
    css = _read_css(template_dir)
    context = {
        "sample": "SAMPLE",
        "assembly": assembly,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance_json": (prov_dir / "tool_versions.json").read_text(encoding="utf-8"),
        "clinvar_vcf": str(clinvar_vcf) if clinvar_vcf else None,
        "qc": qc,
        "important_variants": important,
        "low_confidence": lowc,
        "css": css,
    }

    html_path = out_dir / "report.html"
    pdf_path = out_dir / "report.pdf"
    render_html(template_dir, context, html_path)
    pdf_error = None
    try:
        html_to_pdf(html_path, pdf_path)
    except Exception as exc:
        pdf_error = str(exc)
        log.warning("PDF generation failed; continuing with HTML/JSON outputs. Error: %s", exc)

    if pdf_error:
        context["pdf_error"] = pdf_error

    (out_dir / "report.json").write_text(json.dumps(context, indent=2, default=str), encoding="utf-8")
    if pdf_error:
        typer.echo(f"Wrote: {html_path}")
        typer.echo(f"Wrote: {out_dir / 'report.json'}")
        typer.echo("PDF not generated due to missing WeasyPrint native dependencies.")
    else:
        typer.echo(f"Wrote: {pdf_path}")


@app.command()
def igv(
    vcf: Path = typer.Option(..., exists=True),
    bam: Path = typer.Option(..., exists=True, help="BAM or CRAM"),
    genome: str = typer.Option(..., help="IGV genome id (hg38) or path to fasta"),
    out_dir: Path = typer.Option(Path("out/review"), help="Review bundle directory"),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_dir = out_dir / "snapshots"
    meta_dir = out_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

    low_variants = []
    sample_name = "SAMPLE"

    for v in iter_variants(str(vcf)):
        lc = low_confidence(v)
        if lc.is_low_conf:
            low_variants.append(v)

    if not low_variants:
        typer.echo("No low-confidence variants found. Nothing to snapshot.")
        raise typer.Exit(code=0)

    params = IgvBatchParams(genome=genome, bam_or_cram=str(bam), snapshot_dir=snap_dir)

    bat = out_dir / "igv_batch.igv"
    write_igv_batch(bat, low_variants, params, sample_name=sample_name)
    run_igv_batch(bat)

    manifest = []
    for v in low_variants:
        manifest.append(
            {
                "chrom": v.chrom,
                "pos": v.pos,
                "ref": v.ref,
                "alt": v.alt,
                "gt": v.gt,
                "dp": v.dp,
                "gq": v.gq,
                "locus": f"{v.chrom}:{v.pos}",
            }
        )
    (out_dir / "low_confidence.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    typer.echo(f"Wrote snapshots to: {snap_dir}")


@app.command()
def triage(
    review_dir: Path = typer.Option(Path("out/review"), exists=True),
    out_json: Path = typer.Option(Path("out/review/triage.json")),
):
    snap_dir = review_dir / "snapshots"
    manifest_path = review_dir / "low_confidence.json"
    if not manifest_path.exists():
        raise InputValidationError("Missing low_confidence.json. Run `clinreport igv` first.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []

    for item in manifest:
        chrom = item["chrom"]
        pos = item["pos"]
        matches = sorted(snap_dir.glob(f"*_{chrom}_{pos}_*.png"))
        if not matches:
            matches = sorted(snap_dir.glob(f"*{chrom}*{pos}*.png"))
        if not matches:
            item["triage_error"] = "snapshot_not_found"
            results.append(item)
            continue

        snap = matches[0]
        metadata = {
            "locus": item["locus"],
            "gt": item.get("gt"),
            "dp": item.get("dp"),
            "gq": item.get("gq"),
            "note": "Human review required. Do not use as sole basis for clinical decisions.",
        }
        tri = triage_snapshot(snap, metadata)
        results.append(tri.model_dump())

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    typer.echo(f"Wrote: {out_json}")
