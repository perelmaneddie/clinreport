# Reviewer Workflow

1. Generate report (legacy compatible):
   - `clinreport run ...`
2. Build packet for reviewer:
   - `clinreport review-packet --case-id <case> --report-json <report.json> --out-json <packet.json> --out-md <packet.md>`
3. Record reviewer decision:
   - `clinreport signoff --case-id <case> --variant-id <vid> --reviewer <id> --decision approve|reject|escalate ...`
4. Export final report (requires sign-off):
   - `clinreport final-export --case-id <case> --report-json <report.json> --packet-json <packet.json> --decisions-json <signoff_decisions.json>`

No final export is allowed without explicit sign-off for the variant in packet.
