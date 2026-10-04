# Vaccine Restore Drill

This document records the post-release restore-on-clean-workspace drill.

## Restore model

A clean Git clone alone is not sufficient because private replay artifacts are intentionally not committed. The valid restore model is:

```text
git clone + local private/checkpoint artifacts -> restored workspace -> hermes vaccine-full-gate PASS
```

## Result

- Status: `PASS`
- Definition of Done: `True`
- Clean clone gate: `True`
- Redaction violations: `0`

## Manual verification

1. Open the checkpoint directory for Sprint 14.
2. Inspect `sprint14_restore_drill.summary.json`.
3. Confirm `clean_clone_gate.passed = true`.
4. Confirm `public_redaction_clean = true`.
5. Re-run `hermes vaccine-full-gate` from the main repo.

## Boundary

Controlled lab reproducibility only. This is not a production WAF deployment or broad SQLi protection claim.
