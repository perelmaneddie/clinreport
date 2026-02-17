from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings
from ..exceptions import ExternalToolError


def run_igv_batch(batch_file: Path, igv_sh_path: str | None = None) -> None:
    igv = igv_sh_path or settings.igv_sh_path
    cmd = [igv, "--batch", batch_file.as_posix()]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise ExternalToolError(f"IGV batch failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
