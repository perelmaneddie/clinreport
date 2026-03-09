from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings
from ..exceptions import ExternalToolError


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ExternalToolError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )


def call_variants_from_fastq(
    fastq1: str,
    fastq2: str | None,
    reference_fasta: str,
    out_dir: Path,
    threads: int = 4,
    target_bed: str | None = None,
    min_mapq: int = 0,
    min_baseq: int = 0,
    max_depth: int = 8000,
) -> Path:
    """
    Calls variants from FASTQ by:
      1) mapping with minimap2
      2) sorting/indexing with samtools
      3) calling variants with bcftools
    Returns path to bgzipped VCF.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    bam_path = out_dir / "fastq_called.sorted.bam"
    vcf_path = out_dir / "fastq_called.vcf.gz"

    ref_for_mapping = reference_fasta
    mmi_candidate = f"{reference_fasta}.mmi"
    if Path(mmi_candidate).exists():
        ref_for_mapping = mmi_candidate

    map_cmd = [
        settings.minimap2_path,
        "-a",
        "-x",
        "sr",
        "-t",
        str(threads),
        ref_for_mapping,
        fastq1,
    ]
    if fastq2:
        map_cmd.append(fastq2)

    p1 = subprocess.Popen(map_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    sort_cmd = [
        settings.samtools_path,
        "sort",
        "-@",
        str(threads),
        "-o",
        str(bam_path),
        "-",
    ]
    p2 = subprocess.Popen(sort_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if p1.stdout is not None:
        p1.stdout.close()
    p2.wait()
    p1.wait()

    if p1.returncode != 0:
        raise ExternalToolError(
            "minimap2 mapping failed."
        )
    if p2.returncode != 0:
        raise ExternalToolError("samtools sort failed.")

    _run([settings.samtools_path, "index", str(bam_path)])

    mpileup_cmd = [
        settings.bcftools_path,
        "mpileup",
        "-f",
        reference_fasta,
        "-q",
        str(min_mapq),
        "-Q",
        str(min_baseq),
        "-d",
        str(max_depth),
        str(bam_path),
        "-Ou",
    ]
    if target_bed:
        mpileup_cmd.extend(["-R", target_bed])
    call_cmd = [
        settings.bcftools_path,
        "call",
        "-m",
        "-v",
        "-Oz",
        "-o",
        str(vcf_path),
    ]
    p3 = subprocess.Popen(mpileup_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p4 = subprocess.Popen(call_cmd, stdin=p3.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if p3.stdout is not None:
        p3.stdout.close()
    p4.wait()
    p3.wait()

    if p3.returncode != 0:
        raise ExternalToolError("bcftools mpileup failed.")
    if p4.returncode != 0:
        raise ExternalToolError("bcftools call failed.")

    _run([settings.tabix_path, "-f", "-p", "vcf", str(vcf_path)])
    return vcf_path
