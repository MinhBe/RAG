
# Hermes Vaccine Lab Replay Instructions

## Full local validation

```powershell
Set-Location 'C:\Users\Admin\Documents\Hermes'
uv run python scripts/run_vaccine_gate.py
uv run ruff check app scripts tests
uv run pytest -q
```

## Regenerate staged artifacts

```powershell
uv run python scripts/run_boolean_vaccine_full_dod.py
uv run --with openpyxl python scripts/run_vaccine_sprints_2_3_4.py
uv run --with scikit-learn --with joblib --with paramiko python scripts/run_vaccine_sprints_5_6_7.py
uv run --with openpyxl python scripts/run_vaccine_sprints_8_9_10.py
```

## Expected summary statuses

```text
full_definition_of_done.summary.json -> PASS
sprints_2_3_4_definition_of_done.summary.json -> PASS
sprints_5_6_7_definition_of_done.summary.json -> PASS
sprints_8_9_10_definition_of_done.summary.json -> PASS
```
