
# Hermes Vaccine Lab Troubleshooting

## Gate artifact missing

Run the prerequisite sprint again and verify the expected summary path. Sprint 6 writes `artifacts/vaccine_sprints_5_6_7/sprint6_vaccine_gate.summary.json`.

## `ModuleNotFoundError: paramiko`

The live reward loop uses SSH. Run Sprint 5-7 with:

```powershell
uv run --with scikit-learn --with joblib --with paramiko python scripts/run_vaccine_sprints_5_6_7.py
```

## Excel dependency missing

Review workbook generation needs openpyxl:

```powershell
uv run --with openpyxl python scripts/run_vaccine_sprints_8_9_10.py
```

## WAF/backend check fails

Re-run the safe backend deployment verifier:

```powershell
uv run --with paramiko python scripts/deploy_safe_boolean_oracle_backend.py --verify-only
```

Do not switch to unsafe arbitrary vulnerable endpoints. This lab uses the safe restricted Boolean oracle.

## Public redaction failure

Do not print or commit private replay files. Public artifacts should use hash/signature/feature fields only.
