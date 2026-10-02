# Hermes A — Core post-audit lane

Hermes A is the core application/post-audit lane. It is not the SeqGAN/Security
Demo B lab path.

## Implemented slice

`case/evidence input -> schema validation -> deterministic triage -> analyst draft -> policy/HITL gate -> trace JSONL -> JSON/HTML report`

## Run locally

```powershell
uv run python scripts/run_hermes_a_demo.py
```

Sample input:

```text
data/public/hermes_a_sample_case.json
```

Generated local artifacts:

```text
artifacts/hermes_a/CASE-A-001_report.json
artifacts/hermes_a/CASE-A-001_report.html
artifacts/hermes_a/runs/<request_id>/trace.jsonl
```

## API

```text
POST /v1/cases/process
```

Body shape:

```json
{"case": {"case_id": "CASE-A-001", "title": "...", "evidence": []}}
```

## Boundary

The output is an analyst draft. Hermes A does not confirm a threat, close a
case, escalate autonomously, change a security control, delete data, send
messages, or remediate production.
