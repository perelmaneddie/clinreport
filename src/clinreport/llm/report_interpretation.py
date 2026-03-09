from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import settings
from ..exceptions import InputValidationError


def _extract_text_output(resp: Any) -> str:
    text = ""
    for item in resp.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "output_text":
                    text += content.text
    return text


def interpret_report_json(
    report_path: Path,
    out_json: Path,
    out_md: Path,
    model: str | None = None,
) -> dict[str, Any]:
    if "OPENAI_API_KEY" not in os.environ:
        raise InputValidationError("OPENAI_API_KEY is not set.")

    raw = report_path.read_text(encoding="utf-8")
    report_data = json.loads(raw)
    minified = json.dumps(report_data, separators=(",", ":"))

    prompt = {
        "task": "Interpret variant report for clinician-facing review support",
        "requirements": [
            "Do not provide a diagnosis.",
            "Provide evidence-based interpretation and uncertainty.",
            "Flag limitations and quality caveats clearly.",
            "Human review is required for all findings.",
        ],
        "output_schema": {
            "summary": "string",
            "key_findings": ["string"],
            "priority_variants": [
                {
                    "locus": "string",
                    "gene": "string",
                    "classification": "string",
                    "why_it_matters": "string",
                    "confidence": "low|medium|high",
                }
            ],
            "quality_notes": ["string"],
            "recommended_follow_up": ["string"],
            "disclaimer": "string",
        },
        "report_json": minified,
    }

    client = OpenAI()
    resp = client.responses.create(
        model=model or settings.openai_model,
        instructions=(
            "You are a genomics interpretation assistant. "
            "You must not provide diagnosis or treatment decisions. "
            "Provide a cautious interpretation summary for human review only. "
            "Return strict JSON matching the provided schema."
        ),
        input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt)}]}],
        timeout=settings.openai_timeout_s,
    )
    text = _extract_text_output(resp)
    parsed = json.loads(text)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    md_lines = [
        "# GPT Interpretation",
        "",
        "## Summary",
        parsed.get("summary", ""),
        "",
        "## Key Findings",
    ]
    for item in parsed.get("key_findings", []):
        md_lines.append(f"- {item}")
    md_lines.append("")
    md_lines.append("## Priority Variants")
    for v in parsed.get("priority_variants", []):
        md_lines.append(
            f"- {v.get('locus','')} | {v.get('gene','')} | {v.get('classification','')} | "
            f"confidence={v.get('confidence','')}: {v.get('why_it_matters','')}"
        )
    md_lines.append("")
    md_lines.append("## Quality Notes")
    for item in parsed.get("quality_notes", []):
        md_lines.append(f"- {item}")
    md_lines.append("")
    md_lines.append("## Recommended Follow-up")
    for item in parsed.get("recommended_follow_up", []):
        md_lines.append(f"- {item}")
    md_lines.append("")
    md_lines.append("## Disclaimer")
    md_lines.append(parsed.get("disclaimer", "Human review required."))
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return parsed
