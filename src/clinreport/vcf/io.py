from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from cyvcf2 import VCF


@dataclass(frozen=True)
class VariantRecord:
    chrom: str
    pos: int
    ref: str
    alt: str
    id: Optional[str]
    qual: Optional[float]
    flt: str
    info: dict
    sample: str
    gt: str
    dp: Optional[int]
    gq: Optional[int]
    ad_ref: Optional[int]
    ad_alt: Optional[int]


def _safe_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, (list, tuple)) and len(x) > 0:
            return int(x[0])
        return int(x)
    except Exception:
        return None


def _sample_format_value(rec, key: str):
    try:
        fmt = rec.format(key)
        if fmt is None or len(fmt) == 0:
            return None
        return fmt[0]
    except Exception:
        return None


def iter_variants(vcf_path: str) -> Iterable[VariantRecord]:
    v = VCF(vcf_path)
    samples = v.samples
    sample = samples[0] if samples else "SAMPLE"

    for rec in v:
        alt = rec.ALT[0] if rec.ALT else ""
        flt = rec.FILTER if rec.FILTER is not None else "PASS"

        gt = rec.genotypes[0] if samples and getattr(rec, "genotypes", None) else None
        gt_str = "./."
        if gt:
            a, b = gt[0], gt[1]
            if a is not None and b is not None:
                sep = "|" if gt[2] else "/"
                gt_str = f"{a}{sep}{b}"

        if samples:
            dp = _safe_int(_sample_format_value(rec, "DP"))
            gq = _safe_int(_sample_format_value(rec, "GQ"))
        else:
            dp = _safe_int(rec.INFO.get("DP"))
            gq = None

        ad = None
        if samples:
            ad = _sample_format_value(rec, "AD")
        ad_ref = _safe_int(ad[0]) if ad is not None and len(ad) > 0 else None
        ad_alt = _safe_int(ad[1]) if ad is not None and len(ad) > 1 else None

        yield VariantRecord(
            chrom=rec.CHROM,
            pos=int(rec.POS),
            ref=rec.REF,
            alt=alt,
            id=rec.ID,
            qual=float(rec.QUAL) if rec.QUAL is not None else None,
            flt=str(flt),
            info=dict(rec.INFO),
            sample=sample,
            gt=gt_str,
            dp=dp,
            gq=gq,
            ad_ref=ad_ref,
            ad_alt=ad_alt,
        )
