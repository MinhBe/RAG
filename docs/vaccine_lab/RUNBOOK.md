
# Hermes Vaccine Lab Runbook

## Preconditions

- Windows repo root: `C:\Users\Admin\Documents\Hermes`
- Ubuntu lab VM reachable at the configured SSH target.
- Safe Boolean oracle backend deployed and reachable through ModSecurity.
- Python managed through `uv`.

## Verify the current lab

```powershell
Set-Location 'C:\Users\Admin\Documents\Hermes'
uv run python scripts/run_vaccine_gate.py
uv run ruff check app scripts tests
uv run pytest -q
```

Expected result:

```text
vaccine gate status: PASS
ruff: PASS
pytest: all tests passed
```

## Replay sprint stages

```powershell
uv run python scripts/run_boolean_vaccine_full_dod.py
uv run --with openpyxl python scripts/run_vaccine_sprints_2_3_4.py
uv run --with scikit-learn --with joblib --with paramiko python scripts/run_vaccine_sprints_5_6_7.py
uv run --with openpyxl python scripts/run_vaccine_sprints_8_9_10.py
uv run python scripts/run_vaccine_sprint_11_docs_pack.py
```

## Analyst review workflow

```powershell
uv run --with openpyxl python scripts/ingest_vaccine_review.py `
  --input artifacts/vaccine_sprints_8_9_10/vaccine_manual_review_smoke.xlsx `
  --output artifacts/vaccine_sprints_8_9_10/review_ingest.summary.json
```

Use the template workbook for real review, then ingest the reviewed workbook. The smoke workbook validates workflow only.
