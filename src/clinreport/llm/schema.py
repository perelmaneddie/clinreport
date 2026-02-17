from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TriageLabel = Literal["needs_human_review", "likely_supported", "likely_artifact", "uncertain"]


class IgvTriageResult(BaseModel):
    locus: str
    snapshot_file: str
    triage: TriageLabel
    visual_signals: list[str] = Field(default_factory=list)
    artifact_signals: list[str] = Field(default_factory=list)
    rationale: str
    uncertainty: Literal["low", "medium", "high"] = "high"
    disclaimer: str
