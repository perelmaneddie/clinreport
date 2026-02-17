from __future__ import annotations

import subprocess

from ..config import settings
from ..exceptions import ExternalToolError


def normalize_vcf(in_vcf: str, out_vcf: str, reference_fasta: str | None = None) -> None:
    cmd = [settings.bcftools_path, "norm", "-m", "-any"]
    if reference_fasta:
        cmd += ["-f", reference_fasta]
    cmd += ["-Oz", "-o", out_vcf, in_vcf]

    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ExternalToolError(f"bcftools norm failed:\n{p.stderr}")

    p2 = subprocess.run(["tabix", "-f", "-p", "vcf", out_vcf], capture_output=True, text=True)
    if p2.returncode != 0:
        raise ExternalToolError(f"tabix failed:\n{p2.stderr}")
