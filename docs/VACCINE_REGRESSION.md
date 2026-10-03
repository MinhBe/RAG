# Hermes vaccine regression

This layer connects the redacted Demo B vaccine dataset to the Hermes A Tier-1
case pipeline. It is a regression/evaluation harness, not model fine-tuning.

## Contract

A row is eligible only when all of these are true:

- payload content is absent and marked redacted;
- payload export is false;
- the sample is controlled-lab only;
- ModSecurity is the first gate;
- WAF access and audit telemetry are present;
- the PostgreSQL truth oracle matched;
- the threat signal is verified and not a public target.

Eligible rows are converted to redacted lab `CaseRecord` objects and passed
through the normal Hermes case pipeline.

## Measurement mode

The benchmark disables external model calls on purpose. This isolates the
deterministic Tier-1 routing and HITL invariants from provider variability.

Run:

```powershell
hermes vaccine
```

or:

```powershell
uv run python scripts/run_vaccine_regression.py
```

Outputs:

```text
artifacts/vaccine_regression/summary.json
artifacts/vaccine_regression/summary.cases.jsonl
```

The summary reports positive-routing recall, HITL coverage, remediation
violations, pipeline errors, and latency.

## Claim boundary

The current dataset contains positive controlled-lab cases only. Therefore it
does not measure false-positive rate, specificity, production SOC accuracy, or
model fine-tuning improvement. The current SeqGAN lineage also still depends on
constrained/oracle-ready projection; this benchmark does not convert that into
a claim of raw SeqGAN generation quality.
