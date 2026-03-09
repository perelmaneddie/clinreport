from __future__ import annotations

import json
from pathlib import Path

from ..core.models import AuditEvent


def append_audit_event(audit_path: Path, event: AuditEvent) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(event.model_dump_json() + "\n")


def load_audit_events(audit_path: Path) -> list[dict]:
    if not audit_path.exists():
        return []
    events = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events
