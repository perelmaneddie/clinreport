# Audit Model

Audit events are written as JSONL records to `audit.jsonl`.

Event examples:
- `review_packet_generated`
- `reviewer_signoff`
- `final_export_generated`

Each event contains:
- `event_type`
- `case_id`
- `variant_id` (optional)
- `timestamp`
- `payload` (structured details)

This enables machine-readable traceability for both automated and human decisions.
