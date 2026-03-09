from __future__ import annotations

from ..core.models import ReviewPacket


REQUIRED_DISCLAIMER = "human review"


def validate_packet(packet: ReviewPacket) -> None:
    text = " ".join(
        [
            packet.summary,
            packet.technical_summary,
            packet.evidence_summary,
            packet.draft_rationale,
            " ".join(packet.recommended_actions),
        ]
    ).lower()
    if REQUIRED_DISCLAIMER not in text:
        raise ValueError("Packet missing explicit human-review language")
