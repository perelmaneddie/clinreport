from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..vcf.io import VariantRecord
from .naming import snapshot_name


@dataclass(frozen=True)
class IgvBatchParams:
    genome: str
    bam_or_cram: str
    snapshot_dir: Path
    window_bp_snv: int = 100
    window_bp_indel: int = 250


def _is_indel(v: VariantRecord) -> bool:
    return len(v.ref) != len(v.alt)


def locus_window(v: VariantRecord, params: IgvBatchParams) -> tuple[int, int]:
    w = params.window_bp_indel if _is_indel(v) else params.window_bp_snv
    start = max(1, v.pos - w)
    end = v.pos + w
    return start, end


def write_igv_batch(
    out_bat: Path,
    variants: Iterable[VariantRecord],
    params: IgvBatchParams,
    sample_name: str,
) -> None:
    params.snapshot_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("new")
    lines.append(f"genome {params.genome}")
    lines.append(f"load {params.bam_or_cram}")
    lines.append(f"snapshotDirectory {params.snapshot_dir.as_posix()}")
    lines.append("setSnapshotPrefs")
    lines.append("collapse")
    lines.append("sort position")

    for v in variants:
        start, end = locus_window(v, params)
        locus = f"{v.chrom}:{start}-{end}"
        lines.append(f"goto {locus}")
        fn = snapshot_name(sample_name, v.chrom, v.pos, v.ref, v.alt)
        lines.append(f"snapshot {fn}")

    lines.append("exit")
    out_bat.write_text("\n".join(lines) + "\n", encoding="utf-8")
