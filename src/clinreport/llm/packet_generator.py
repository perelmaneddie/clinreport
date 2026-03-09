from __future__ import annotations

import json

from openai import OpenAI

from ..config import settings
from ..core.models import AuthenticityAssessment, EvidenceMap, ReviewPacket, VariantRecordModel
from ..exceptions import InputValidationError
from .grounding import grounding_hash
from .validators import validate_packet


class ReviewPacketGenerator:
    def generate(
        self,
        variant: VariantRecordModel,
        authenticity: AuthenticityAssessment,
        evidence_map: EvidenceMap,
        use_llm: bool = False,
    ) -> ReviewPacket:
        payload = {
            "variant": variant.model_dump(),
            "authenticity": authenticity.model_dump(),
            "evidence_map": evidence_map.model_dump(),
        }
        ghash = grounding_hash(payload)

        if use_llm:
            client = OpenAI()
            prompt = {
                "task": "Create reviewer packet",
                "rules": [
                    "Use only provided evidence",
                    "Do not infer unstated facts",
                    "Mark uncertainty clearly",
                    "Human review is required",
                ],
                "payload": payload,
            }
            resp = client.responses.create(
                model=settings.openai_model,
                instructions=(
                    "You summarize structured evidence for human variant review. "
                    "Never provide final sign-out decisions. "
                    "Output strict JSON with fields: summary, technical_summary, evidence_summary, "
                    "conflicts, recommended_actions, draft_rationale."
                ),
                input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt)}]}],
                timeout=settings.openai_timeout_s,
            )
            text = ""
            for item in resp.output:
                if item.type == "message":
                    for c in item.content:
                        if c.type == "output_text":
                            text += c.text
            data = json.loads(text)
        else:
            supports = [f"{x.code}:{x.reason}" for x in evidence_map.supports]
            contradicts = [f"{x.code}:{x.reason}" for x in evidence_map.contradicts]
            data = {
                "summary": (
                    f"Variant {variant.variant_id} routed for human review; "
                    f"state={evidence_map.state}, authenticity={authenticity.label}."
                ),
                "technical_summary": (
                    f"Authenticity score={authenticity.authenticity_score:.2f}, "
                    f"confidence={authenticity.confidence:.2f}, tags={authenticity.artifact_tags}."
                ),
                "evidence_summary": (
                    f"Supports={supports if supports else ['none']}; "
                    f"Contradicts={contradicts if contradicts else ['none']}; "
                    f"Missing={evidence_map.missing if evidence_map.missing else ['none']}."
                ),
                "conflicts": [x.reason for x in evidence_map.contradicts],
                "recommended_actions": [
                    "Human review required before release",
                    "Escalate if conflicting or missing evidence remains",
                ],
                "draft_rationale": (
                    "Draft rationale prepared from deterministic evidence map and technical authenticity; "
                    "human review required for final sign-out."
                ),
            }

        packet = ReviewPacket(
            variant_id=variant.variant_id,
            summary=data.get("summary", ""),
            technical_summary=data.get("technical_summary", ""),
            evidence_summary=data.get("evidence_summary", ""),
            conflicts=list(data.get("conflicts", [])),
            recommended_actions=list(data.get("recommended_actions", [])),
            draft_rationale=data.get("draft_rationale", ""),
            llm_model=settings.openai_model if use_llm else "deterministic-template",
            grounding_hash=ghash,
        )
        try:
            validate_packet(packet)
        except ValueError as exc:
            raise InputValidationError(str(exc))
        return packet
