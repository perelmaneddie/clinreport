# Architecture

`clinreport` now follows a review-centric pipeline:

1. Input ingestion (`run` and report JSON)
2. Technical authenticity assessment (`technical_review/authenticity_engine.py`)
3. Deterministic evidence mapping (`evidence_mapping/engine.py`)
4. Review packet generation (`llm/packet_generator.py`)
5. Human sign-off (`review/signoff.py`)
6. Final export gated by sign-off (`final-export` CLI)

LLMs are used for evidence packaging only. Deterministic rule logic remains the clinical backbone.
