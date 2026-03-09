from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import typer

from .exceptions import InputValidationError
from .core.models import (
    AuditEvent,
    ReviewerDecision,
    TechnicalEvidence,
    VariantRecordModel,
)
from .evidence_mapping.engine import EvidenceMappingEngine
from .igv.batch import IgvBatchParams, write_igv_batch
from .igv.runner import run_igv_batch
from .llm.report_interpretation import interpret_report_json
from .llm.packet_generator import ReviewPacketGenerator
from .llm.openai_triage import triage_snapshot
from .logging_utils import setup_logging
from .provenance import collect_versions, write_provenance
from .qc.fastq_qc import run_fastp
from .qc.fastq_variants import call_variants_from_fastq
from .report.render import html_to_pdf, render_html
from .review.audit import append_audit_event
from .review.routing import route_review_queue
from .review.signoff import has_signoff, save_reviewer_decision
from .technical_review.authenticity_engine import TechnicalAuthenticityEngine
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
    vcf: Path | None = typer.Option(
        None, help="Input VCF (prefer bgzipped + indexed). Optional if FASTQ + reference is provided."
    ),
    assembly: str = typer.Option("GRCh38", help="Reference build label for report"),
    out_dir: Path = typer.Option(Path("out"), help="Output directory"),
    fastq1: Path | None = typer.Option(None, exists=True, help="FASTQ R1 (optional QC)"),
    fastq2: Path | None = typer.Option(None, exists=True, help="FASTQ R2 (optional QC)"),
    reference_fasta: Path | None = typer.Option(
        None,
        help="Reference FASTA required when calling variants from FASTQ.",
    ),
    caller_threads: int = typer.Option(4, min=1, help="Threads for FASTQ variant calling."),
    target_bed: Path | None = typer.Option(
        None,
        help="Optional BED file to restrict FASTQ variant calling regions (major speed-up).",
    ),
    fast_call_preset: bool = typer.Option(
        False,
        help="Use faster (less sensitive) calling thresholds for FASTQ mode.",
    ),
    skip_fastq_qc: bool = typer.Option(
        False,
        help="Skip fastp QC for faster end-to-end runtime.",
    ),
    clinvar_vcf: Path | None = typer.Option(
        None,
        exists=True,
        help="Optional ClinVar VCF.gz for annotation (e.g. clinvar.vcf.gz GRCh38)",
    ),
):
    if vcf is None and fastq1 is None:
        raise InputValidationError("Provide at least one input source: --vcf or --fastq1.")
    if vcf is not None and not vcf.exists():
        raise InputValidationError(f"VCF file not found: {vcf}")
    if fastq1 is not None and reference_fasta is None:
        raise InputValidationError("--reference-fasta is required when --fastq1 is provided.")
    if reference_fasta is not None and not reference_fasta.exists():
        raise InputValidationError(f"Reference FASTA not found: {reference_fasta}")
    if target_bed is not None and not target_bed.exists():
        raise InputValidationError(f"Target BED not found: {target_bed}")

    out_dir.mkdir(parents=True, exist_ok=True)
    min_mapq = 20 if fast_call_preset else 0
    min_baseq = 20 if fast_call_preset else 0
    max_depth = 250 if fast_call_preset else 8000

    fastq_called_vcf: Path | None = None
    if fastq1 is not None:
        fastq_call_dir = out_dir / "fastq_calling"
        fastq_called_vcf = call_variants_from_fastq(
            fastq1=str(fastq1),
            fastq2=str(fastq2) if fastq2 else None,
            reference_fasta=str(reference_fasta),
            out_dir=fastq_call_dir,
            threads=caller_threads,
            target_bed=str(target_bed) if target_bed else None,
            min_mapq=min_mapq,
            min_baseq=min_baseq,
            max_depth=max_depth,
        )
        log.info("FASTQ-derived variants written to %s", fastq_called_vcf)

    analysis_vcf = vcf if vcf is not None else fastq_called_vcf
    if analysis_vcf is None:
        raise InputValidationError("No analyzable VCF available after FASTQ processing.")

    versions = collect_versions()
    prov_dir = out_dir / "metadata"
    write_provenance(
        prov_dir,
        versions,
        extra={
            "assembly": assembly,
            "vcf": str(analysis_vcf),
            "input_vcf": str(vcf) if vcf else None,
            "fastq_called_vcf": str(fastq_called_vcf) if fastq_called_vcf else None,
            "target_bed": str(target_bed) if target_bed else None,
            "fast_call_preset": fast_call_preset,
        },
    )

    qc = None
    if fastq1 and not skip_fastq_qc:
        qc = run_fastp(str(fastq1), str(fastq2) if fastq2 else None, out_dir / "qc")

    important = []
    lowc = []
    clinvar_matcher = ClinVarStreamMatcher(str(clinvar_vcf)) if clinvar_vcf else None

    for v in iter_variants(str(analysis_vcf)):
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

    fastq_detected_variants = []
    if fastq_called_vcf is not None:
        for v in iter_variants(str(fastq_called_vcf)):
            fastq_detected_variants.append(
                {
                    "chrom": v.chrom,
                    "pos": v.pos,
                    "ref": v.ref,
                    "alt": v.alt,
                    "gt": v.gt,
                    "dp": v.dp,
                    "gq": v.gq,
                }
            )

    template_dir = Path(__file__).parent / "report" / "templates"
    css = _read_css(template_dir)
    context = {
        "sample": "SAMPLE",
        "assembly": assembly,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance_json": (prov_dir / "tool_versions.json").read_text(encoding="utf-8"),
        "analysis_vcf": str(analysis_vcf),
        "clinvar_vcf": str(clinvar_vcf) if clinvar_vcf else None,
        "fastq_called_vcf": str(fastq_called_vcf) if fastq_called_vcf else None,
        "qc": qc,
        "important_variants": important,
        "fastq_detected_variants": fastq_detected_variants,
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


@app.command("interpret-report")
def interpret_report(
    report_json: Path = typer.Option(..., exists=True, help="Input clinreport JSON report"),
    out_json: Path = typer.Option(Path("out/interpretation/interpretation.json")),
    out_md: Path = typer.Option(Path("out/interpretation/interpretation.md")),
    model: str | None = typer.Option(None, help="Override model (default CLINREPORT_OPENAI_MODEL)"),
):
    parsed = interpret_report_json(
        report_path=report_json,
        out_json=out_json,
        out_md=out_md,
        model=model,
    )
    typer.echo(f"Wrote: {out_json}")
    typer.echo(f"Wrote: {out_md}")
    typer.echo(f"Summary: {parsed.get('summary', '')[:200]}")


def _variant_id(chrom: str, pos: int, ref: str, alt: str) -> str:
    return f"{chrom}-{pos}-{ref}-{alt}"


@app.command("review-packet")
def review_packet(
    case_id: str = typer.Option(..., help="Case identifier"),
    report_json: Path = typer.Option(..., exists=True, help="Input report.json"),
    out_json: Path = typer.Option(Path("out/review/packet.json")),
    out_md: Path = typer.Option(Path("out/review/packet.md")),
    use_llm: bool = typer.Option(False, help="Use LLM for packet generation"),
):
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    variants = payload.get("important_variants") or payload.get("fastq_detected_variants") or []
    if not variants:
        raise InputValidationError("No variants found in report for packet generation.")

    first = variants[0]
    vid = _variant_id(first["chrom"], int(first["pos"]), first["ref"], first["alt"])
    variant = VariantRecordModel(
        variant_id=vid,
        chrom=first["chrom"],
        pos=int(first["pos"]),
        ref=first["ref"],
        alt=first["alt"],
        gene=first.get("gene"),
        clinvar=first.get("clinvar"),
        gt=first.get("gt"),
        dp=first.get("dp"),
        gq=first.get("gq"),
        filter=first.get("filter"),
    )
    evidence = TechnicalEvidence(
        dp=first.get("dp"),
        gq=first.get("gq"),
        vaf=first.get("vaf"),
    )

    auth_engine = TechnicalAuthenticityEngine()
    authenticity = auth_engine.assess(variant, evidence)

    mapping_engine = EvidenceMappingEngine()
    evidence_map = mapping_engine.map(
        variant,
        annotations={"clinvar": first.get("clinvar"), "consequence": first.get("consequence")},
        authenticity=authenticity,
    )
    queue = route_review_queue(authenticity, evidence_map)

    packet_gen = ReviewPacketGenerator()
    packet = packet_gen.generate(variant, authenticity, evidence_map, use_llm=use_llm)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    packet_payload = {
        "case_id": case_id,
        "queue": queue,
        "variant": variant.model_dump(),
        "authenticity": authenticity.model_dump(),
        "evidence_map": evidence_map.model_dump(),
        "packet": packet.model_dump(),
    }
    out_json.write_text(json.dumps(packet_payload, indent=2), encoding="utf-8")
    out_md.write_text(
        "\n".join(
            [
                f"# Review Packet: {case_id}",
                "",
                f"Variant: `{vid}`",
                f"Queue: `{queue}`",
                "",
                "## Summary",
                packet.summary,
                "",
                "## Technical",
                packet.technical_summary,
                "",
                "## Evidence",
                packet.evidence_summary,
                "",
                "## Recommended Actions",
                *[f"- {x}" for x in packet.recommended_actions],
                "",
                "## Draft Rationale",
                packet.draft_rationale,
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    append_audit_event(
        out_json.parent / "audit.jsonl",
        AuditEvent(
            event_type="review_packet_generated",
            case_id=case_id,
            variant_id=vid,
            payload={"queue": queue, "use_llm": use_llm, "packet_path": str(out_json)},
        ),
    )
    typer.echo(f"Wrote: {out_json}")
    typer.echo(f"Wrote: {out_md}")
    typer.echo(f"Queue: {queue}")


@app.command("signoff")
def signoff(
    case_id: str = typer.Option(..., help="Case identifier"),
    variant_id: str = typer.Option(..., help="Variant ID, e.g. chr7-140453136-A-T"),
    reviewer: str = typer.Option(..., help="Reviewer identity"),
    decision: str = typer.Option(..., help="approve|reject|escalate|request_more_evidence|mark_orthogonal_confirmation|defer"),
    comment: str = typer.Option("", help="Reviewer comment"),
    override: bool = typer.Option(False, help="Override system recommendation"),
    escalation_reason: str | None = typer.Option(None, help="Reason for escalation"),
    out_dir: Path = typer.Option(Path("out/review"), help="Review output directory"),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    decision_obj = ReviewerDecision(
        case_id=case_id,
        variant_id=variant_id,
        reviewer=reviewer,
        decision=decision,  # pydantic validates accepted values
        comment=comment,
        override=override,
        escalation_reason=escalation_reason,
    )
    decisions_path = out_dir / "signoff_decisions.json"
    save_reviewer_decision(decisions_path, decision_obj)
    append_audit_event(
        out_dir / "audit.jsonl",
        AuditEvent(
            event_type="reviewer_signoff",
            case_id=case_id,
            variant_id=variant_id,
            payload=decision_obj.model_dump(),
        ),
    )
    typer.echo(f"Wrote: {decisions_path}")
    typer.echo("Sign-off recorded.")


@app.command("final-export")
def final_export(
    case_id: str = typer.Option(..., help="Case identifier"),
    report_json: Path = typer.Option(..., exists=True, help="Original report.json"),
    packet_json: Path = typer.Option(..., exists=True, help="Review packet JSON"),
    decisions_json: Path = typer.Option(Path("out/review/signoff_decisions.json"), exists=True),
    out_json: Path = typer.Option(Path("out/review/final_report.json")),
):
    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    variant_id = packet["variant"]["variant_id"]
    if not has_signoff(decisions_json, case_id, variant_id):
        raise InputValidationError(
            f"No reviewer sign-off for case={case_id}, variant={variant_id}. Final export is blocked."
        )

    report = json.loads(report_json.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
    out_payload = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "variant_id": variant_id,
        "report": report,
        "review_packet": packet,
        "reviewer_decisions": decisions.get("decisions", []),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    append_audit_event(
        out_json.parent / "audit.jsonl",
        AuditEvent(
            event_type="final_export_generated",
            case_id=case_id,
            variant_id=variant_id,
            payload={"out_json": str(out_json)},
        ),
    )
    typer.echo(f"Wrote: {out_json}")
