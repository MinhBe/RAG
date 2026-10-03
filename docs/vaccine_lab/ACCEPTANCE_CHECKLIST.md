# Vaccine Lab Acceptance Checklist

Generated: 2026-10-03T23:30:11.058112+00:00

## Release command

```powershell
.\hermes.cmd vaccine-full-gate
```

Expected: `status = PASS`, `definition_of_done_passed = true`, and `git_release_state_clean = true`.

## Manual acceptance items

- [ ] Confirm `final_release_gate.summary.json` reports `PASS`.
- [ ] Confirm all previous sprint summaries report `PASS`.
- [ ] Confirm the checkpoint ZIP exists: `43_VACCINE_SPRINT_12_FINAL_RELEASE_PASS_20261004.zip`.
- [ ] Confirm `release_integrity_manifest.jsonl` contains SHA256 values for docs, scripts, summaries, and checkpoint.
- [ ] Confirm public docs do not contain raw payloads.
- [ ] Confirm private replay artifacts remain local-only.
- [ ] Confirm claim boundary remains controlled lab only.
- [ ] Confirm git working tree is clean before calling this a sealed release.

## Latest final gate

```json
{
  "passed": true,
  "returncode": 0
}
```

## Integrity manifest

Manifest path:

```text
artifacts\vaccine_acceptance_seal\release_integrity_manifest.jsonl
```

Manifest rows: 18
Missing rows: 0

## Claim boundary

Controlled lab artifacts only. This is not a production WAF deployment, not broad SQLi protection, and not a claim that vendor full raw SeqGAN self-generated all accepted samples.
