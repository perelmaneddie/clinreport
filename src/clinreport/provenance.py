from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from . import __version__


@dataclass
class ToolVersions:
    clinreport: str
    python: str
    os: str
    bcftools: Optional[str] = None
    igv: Optional[str] = None
    fastp: Optional[str] = None


def _run_version(cmd: list[str]) -> Optional[str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        out = out.strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


def collect_versions(bcftools_path="bcftools", igv_sh_path="igv.sh", fastp_path="fastp") -> ToolVersions:
    return ToolVersions(
        clinreport=__version__,
        python=platform.python_version(),
        os=f"{platform.system()} {platform.release()}",
        bcftools=_run_version([bcftools_path, "--version"]),
        igv=_run_version([igv_sh_path, "--help"]),
        fastp=_run_version([fastp_path, "--version"]),
    )


def write_provenance(out_dir: Path, versions: ToolVersions, extra: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"versions": asdict(versions), "extra": extra}
    (out_dir / "tool_versions.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
