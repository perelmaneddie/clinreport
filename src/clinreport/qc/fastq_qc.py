from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..config import settings
from ..exceptions import ExternalToolError


def run_fastp(r1: str, r2: str | None, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "fastp.json"
    html_path = out_dir / "fastp.html"

    cmd = [settings.fastp_path, "-i", r1, "-j", str(json_path), "-h", str(html_path)]
    if r2:
        cmd += ["-I", r2]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ExternalToolError(f"fastp failed:\n{p.stderr}")

    return json.loads(json_path.read_text(encoding="utf-8"))
