from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import settings
from .io import VariantRecord


@dataclass(frozen=True)
class LowConfidenceFlag:
    is_low_conf: bool
    reasons: list[str]


def allele_balance(ad_ref: Optional[int], ad_alt: Optional[int]) -> Optional[float]:
    if ad_ref is None or ad_alt is None:
        return None
    denom = ad_ref + ad_alt
    if denom <= 0:
        return None
    return ad_alt / denom


def low_confidence(v: VariantRecord) -> LowConfidenceFlag:
    r = settings.rules
    reasons: list[str] = []

    if v.flt not in ("PASS", ".", ""):
        reasons.append(f"FILTER={v.flt}")

    if v.dp is not None and v.dp < r.min_dp:
        reasons.append(f"DP<{r.min_dp} (DP={v.dp})")
    if v.gq is not None and v.gq < r.min_gq:
        reasons.append(f"GQ<{r.min_gq} (GQ={v.gq})")

    ab = allele_balance(v.ad_ref, v.ad_alt)
    if ab is not None:
        if v.gt in ("0/1", "1/0") and (ab < 0.2 or ab > 0.8):
            reasons.append(f"AlleleBalanceOutOfRange (AB={ab:.2f})")

    return LowConfidenceFlag(is_low_conf=len(reasons) > 0, reasons=reasons)
