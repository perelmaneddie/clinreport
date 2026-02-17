# clinreport

Local clinical variant report generator with IGV review bundle.

## Install
pip install -e .

## Run report
clinreport run --vcf patient.vcf.gz --out-dir out

## Create IGV snapshots for low-confidence variants
clinreport igv --vcf patient.vcf.gz --bam patient.bam --genome hg38 --out-dir out/review

## Optional: LLM triage notes (human review required)
export OPENAI_API_KEY=...
clinreport triage --review-dir out/review --out-json out/review/triage.json
