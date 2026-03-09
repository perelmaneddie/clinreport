from __future__ import annotations

import json
from pathlib import Path

from ..core.models import ReviewerDecision


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {"decisions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_reviewer_decision(path: Path, decision: ReviewerDecision) -> None:
    payload = _read_json(path)
    payload.setdefault("decisions", [])
    payload["decisions"].append(decision.model_dump())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def has_signoff(path: Path, case_id: str, variant_id: str) -> bool:
    payload = _read_json(path)
    for item in payload.get("decisions", []):
        if item.get("case_id") == case_id and item.get("variant_id") == variant_id:
            return True
    return False
