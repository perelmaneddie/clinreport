from __future__ import annotations

import re


def safe_token(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s.strip("_")


def snapshot_name(sample: str, chrom: str, pos: int, ref: str, alt: str) -> str:
    return f"{safe_token(sample)}_{safe_token(chrom)}_{pos}_{safe_token(ref)}_{safe_token(alt)}.png"
