from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import settings
from .schema import IgvTriageResult


def _b64_png(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode("ascii")


def triage_snapshot(snapshot_path: Path, metadata: dict[str, Any]) -> IgvTriageResult:
    client = OpenAI()

    system_instructions = (
        "You are assisting with variant review triage. "
        "You MUST NOT provide a medical diagnosis. "
        "You may describe visual signals in IGV that could suggest support or artifact, "
        "but always require human review. Output must be valid JSON matching the schema."
    )

    prompt = {
        "task": "IGV triage (human review required)",
        "metadata": metadata,
        "output_schema": {
            "locus": "string",
            "snapshot_file": "string",
            "triage": "needs_human_review|likely_supported|likely_artifact|uncertain",
            "visual_signals": ["string"],
            "artifact_signals": ["string"],
            "rationale": "string",
            "uncertainty": "low|medium|high",
            "disclaimer": "string",
        },
    }

    b64 = _b64_png(snapshot_path)
    resp = client.responses.create(
        model=settings.openai_model,
        instructions=system_instructions,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": json.dumps(prompt)},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
                ],
            }
        ],
        timeout=settings.openai_timeout_s,
    )

    text = ""
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    text += c.text

    data = json.loads(text)
    return IgvTriageResult(**data)
