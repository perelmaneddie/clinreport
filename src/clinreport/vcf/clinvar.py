from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cyvcf2 import VCF

from .io import VariantRecord


def _norm_chrom(chrom: str) -> str:
    c = chrom.strip()
    if c.lower().startswith("chr"):
        return c[3:]
    return c


def _chrom_rank(chrom: str) -> tuple[int, str]:
    c = _norm_chrom(chrom).upper()
    if c.isdigit():
        return (0, f"{int(c):03d}")
    special = {"X": "023", "Y": "024", "M": "025", "MT": "025"}
    if c in special:
        return (0, special[c])
    return (1, c)


def _locus_key(chrom: str, pos: int) -> tuple[tuple[int, str], int]:
    return (_chrom_rank(chrom), pos)


@dataclass(frozen=True)
class ClinVarHit:
    clnsig: str
    gene: str


class ClinVarStreamMatcher:
    """
    Streaming matcher for sorted patient and ClinVar VCFs.

    It advances ClinVar records in lockstep with patient variants and caches
    all records at the current ClinVar locus to avoid repeated random lookups.
    """

    def __init__(self, clinvar_vcf_path: str):
        self._cv = VCF(clinvar_vcf_path)
        self._iter = iter(self._cv)
        self._current = next(self._iter, None)
        self._cached_locus: Optional[tuple[tuple[int, str], int]] = None
        self._cached_records = []

    def _read_locus_records(self, locus: tuple[tuple[int, str], int]) -> None:
        self._cached_locus = locus
        self._cached_records = []
        while self._current is not None and _locus_key(self._current.CHROM, int(self._current.POS)) == locus:
            self._cached_records.append(self._current)
            self._current = next(self._iter, None)

    def match(self, v: VariantRecord) -> Optional[ClinVarHit]:
        target_locus = _locus_key(v.chrom, v.pos)

        while self._current is not None and _locus_key(self._current.CHROM, int(self._current.POS)) < target_locus:
            self._current = next(self._iter, None)

        if self._current is None:
            return None

        current_locus = _locus_key(self._current.CHROM, int(self._current.POS))
        if current_locus != target_locus and self._cached_locus != target_locus:
            return None

        if self._cached_locus != target_locus:
            self._read_locus_records(target_locus)

        clnsigs: list[str] = []
        genes: list[str] = []
        for rec in self._cached_records:
            if rec.REF != v.ref:
                continue
            if not rec.ALT:
                continue
            if v.alt not in rec.ALT:
                continue
            clnsig = str(rec.INFO.get("CLNSIG", "")).strip()
            geneinfo = str(rec.INFO.get("GENEINFO", "")).strip()
            if clnsig:
                clnsigs.append(clnsig)
            if geneinfo:
                # GENEINFO looks like: "CFTR:1080|ASZ1:..." -> keep gene symbols only.
                symbols = []
                for item in geneinfo.split("|"):
                    sym = item.split(":", 1)[0].strip()
                    if sym:
                        symbols.append(sym)
                genes.extend(symbols)

        if not clnsigs and not genes:
            return None

        uniq_clnsig = sorted(set(clnsigs))
        uniq_genes = sorted(set(genes))
        return ClinVarHit(clnsig="|".join(uniq_clnsig), gene="|".join(uniq_genes))
