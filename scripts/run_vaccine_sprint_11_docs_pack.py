from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(".")
DOCS = Path("docs/vaccine_lab")
OUT = Path("artifacts/vaccine_sprint_11")

SUMMARY_FILES = {
    "sprint1": Path("artifacts/boolean_vaccine/full_definition_of_done.summary.json"),
    "sprint2_4": Path("artifacts/vaccine_sprints_2_3_4/sprints_2_3_4_definition_of_done.summary.json"),
    "sprint5_7": Path("artifacts/vaccine_sprints_5_6_7/sprints_5_6_7_definition_of_done.summary.json"),
    "sprint8_10": Path("artifacts/vaccine_sprints_8_9_10/sprints_8_9_10_definition_of_done.summary.json"),
}
RAW_FIELD_RE = re.compile(r"\b(payload|generated_payload|true_expr|false_expr|expr)\b", re.IGNORECASE)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {"cmd": cmd, "returncode": proc.returncode, "stdout_tail": proc.stdout[-3000:], "stderr_tail": proc.stderr[-3000:]}


def preflight() -> dict[str, Any]:
    summaries = {name: read_json(path) for name, path in SUMMARY_FILES.items()}
    statuses = {name: data.get("status") for name, data in summaries.items()}
    ok = all(status == "PASS" for status in statuses.values())
    docs_ready_inputs = all(path.exists() for path in SUMMARY_FILES.values())
    gate = run([sys.executable, "scripts/run_vaccine_gate.py"])
    gate_ok = gate["returncode"] == 0
    return {
        "ok": ok and docs_ready_inputs and gate_ok,
        "statuses": statuses,
        "required_files_exist": {name: path.exists() for name, path in SUMMARY_FILES.items()},
        "gate_returncode": gate["returncode"],
        "gate_stdout_tail": gate["stdout_tail"],
    }


def docs_contain_raw_payloads(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if RAW_FIELD_RE.search(line) and "raw payload" not in line.lower() and "without raw" not in line.lower():
                violations.append(f"{path}:{line_no}")
    return violations


def architecture_doc() -> str:
    return """
# Hermes Vaccine Lab Architecture

## Scope

This lab validates a controlled defensive vaccine workflow over a safe restricted Boolean oracle behind ModSecurity. Public artifacts are redacted. Private replay artifacts remain local only.

## Data flow

```text
Client / runner
  -> Apache + ModSecurity on Ubuntu lab VM :18080
  -> /bool_oracle
  -> safe Boolean oracle backend :18081
  -> TRUE/FALSE observation
  -> reward / detector / regression artifacts
```

## Sprint ladder

```text
Sprint 1  - Boolean vaccine generation lab
Sprint 2  - Vaccine effectiveness / temporary patch validation
Sprint 3  - Negative/control corpus expansion
Sprint 4  - Multi-family attack grammar expansion
Sprint 5  - SeqGAN adapter lineage and reward loop
Sprint 6  - One-command vaccine regression gate
Sprint 7  - Classical ML baseline
Sprint 8  - Human review workflow
Sprint 9  - Safe deployment modes
Sprint 10 - Drift / mutation robustness
Sprint 11 - Documentation and reproducibility pack
```

## Non-claims

- This is not a production WAF deployment.
- This is not broad SQL injection protection.
- This does not claim vendor full raw SeqGAN self-clean generation.
- Public artifacts must not expose sensitive raw payload material.
"""


def runbook_doc() -> str:
    return """
# Hermes Vaccine Lab Runbook

## Preconditions

- Windows repo root: `C:\\Users\\Admin\\Documents\\Hermes`
- Ubuntu lab VM reachable at the configured SSH target.
- Safe Boolean oracle backend deployed and reachable through ModSecurity.
- Python managed through `uv`.

## Verify the current lab

```powershell
Set-Location 'C:\\Users\\Admin\\Documents\\Hermes'
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
"""


def troubleshooting_doc() -> str:
    return """
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
"""


def artifact_map_doc() -> str:
    checkpoints = [
        "36_SAFE_BOOLEAN_ORACLE_BACKEND_DOD_PASS_20261004.zip",
        "37_BOOLEAN_VACCINE_DOD_REVERIFY_PASS_20261004.zip",
        "38_BOOLEAN_VACCINE_FULL_DOD_PASS_20261004.zip",
        "39_VACCINE_SPRINTS_2_3_4_PASS_20261004.zip",
        "40_VACCINE_SPRINTS_5_6_7_PASS_20261004.zip",
        "41_VACCINE_SPRINTS_8_9_10_PASS_20261004.zip",
        "42_VACCINE_SPRINT_11_DOCS_PASS_20261004.zip",
    ]
    rows = "\n".join(f"- `{item}`" for item in checkpoints)
    return f"""
# Hermes Vaccine Lab Artifact Map

## Checkpoints

{rows}

## Repository scripts

- `scripts/deploy_safe_boolean_oracle_backend.py`
- `scripts/run_boolean_seed_discovery.py`
- `scripts/run_boolean_oracle_generated_probe.py`
- `scripts/run_seqgan_reward_small_loop.py`
- `scripts/run_boolean_vaccine_full_dod.py`
- `scripts/run_vaccine_sprints_2_3_4.py`
- `scripts/run_vaccine_gate.py`
- `scripts/run_vaccine_sprints_5_6_7.py`
- `scripts/ingest_vaccine_review.py`
- `scripts/run_vaccine_sprints_8_9_10.py`
- `scripts/run_vaccine_sprint_11_docs_pack.py`

## Private local roots

- `artifacts/boolean_vaccine/private/`
- `artifacts/vaccine_sprints_2_3_4/private/`
- `artifacts/vaccine_sprints_5_6_7/private/`

Private local roots are excluded from git and should not be shared as public evidence.
"""


def claim_boundary_doc() -> str:
    return """
# Hermes Vaccine Lab Claim Boundary

The valid claim is:

```text
Controlled lab defensive validation over a safe restricted Boolean oracle behind ModSecurity. Public artifacts are redacted. Regression, review, deployment-mode, mutation, and ML-baseline workflows are validated as lab artifacts.
```

Invalid claims:

```text
This is production WAF protection.
This is broad SQL injection protection.
This proves vendor full raw SeqGAN generated clean accepted outputs unaided.
This replaces analyst review.
This can be used safely against public targets.
```

Operational rule:

```text
If a result lacks command output, summary artifact, or replay instructions, it is not considered verified.
```
"""


def replay_doc() -> str:
    return """
# Hermes Vaccine Lab Replay Instructions

## Full local validation

```powershell
Set-Location 'C:\\Users\\Admin\\Documents\\Hermes'
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
"""


def rollback_doc() -> str:
    return """
# Hermes Vaccine Lab Rollback Instructions

Sprint 9 validates artifact-level safe deployment modes:

```text
observe -> detection-only -> blocking -> rollback to observe
```

Rollback evidence is stored in:

```text
artifacts/vaccine_sprints_8_9_10/rollback.summary.json
```

Required evidence:

```text
rollback_from = blocking
rollback_to = observe
health_check_after_rollback = PASS
```

This is an artifact-level deployment-mode validation. It does not mutate a production WAF.
"""


def new_chat_handover_doc() -> str:
    return """
# Hermes Vaccine Lab New Chat Handover

You are continuing a controlled defensive vaccine lab. Do not expose private replay payloads. Do not deploy arbitrary vulnerable endpoints. Use the safe restricted Boolean oracle behind ModSecurity.

Current state through Sprint 11:

```text
Sprint 1: PASS - Boolean vaccine generation lab
Sprint 2: PASS - Vaccine effectiveness / temporary patch validation
Sprint 3: PASS - Negative/control corpus expansion
Sprint 4: PASS - Multi-family attack grammar expansion
Sprint 5: PASS - SeqGAN adapter lineage
Sprint 6: PASS - One-command vaccine gate
Sprint 7: PASS - Classical ML baseline
Sprint 8: PASS - Human review workflow smoke validation
Sprint 9: PASS - Safe deployment modes
Sprint 10: PASS - Drift / mutation robustness
Sprint 11: PASS - Documentation and reproducibility pack
```

Next sprint should be Sprint 12: Final Release Gate.

Minimum checks before moving forward:

```powershell
uv run python scripts/run_vaccine_gate.py
uv run ruff check app scripts tests
uv run pytest -q
```
"""


def generate_docs(pre: dict[str, Any]) -> list[Path]:
    docs = {
        DOCS / "README.md": "# Hermes Vaccine Lab\n\nThis documentation pack covers reproducibility, artifact mapping, replay, rollback, and claim boundaries for the controlled Hermes vaccine lab.\n\nStart with `RUNBOOK.md`, then inspect `ARTIFACT_MAP.md` and `CLAIM_BOUNDARY.md`.\n",
        DOCS / "ARCHITECTURE.md": architecture_doc(),
        DOCS / "RUNBOOK.md": runbook_doc(),
        DOCS / "TROUBLESHOOTING.md": troubleshooting_doc(),
        DOCS / "ARTIFACT_MAP.md": artifact_map_doc(),
        DOCS / "CLAIM_BOUNDARY.md": claim_boundary_doc(),
        DOCS / "REPLAY.md": replay_doc(),
        DOCS / "ROLLBACK.md": rollback_doc(),
        DOCS / "NEW_CHAT_HANDOVER.md": new_chat_handover_doc(),
    }
    for path, text in docs.items():
        write_text(path, text)
    write_json(OUT / "sprint11_preflight.summary.json", pre)
    return list(docs)


def main() -> None:
    pre = preflight()
    if not pre["ok"]:
        write_json(OUT / "sprint11_preflight.summary.json", pre)
        print(json.dumps({"status": "FAIL", "preflight": pre}, indent=2, sort_keys=True))
        raise SystemExit(1)
    doc_paths = generate_docs(pre)
    violations = docs_contain_raw_payloads(doc_paths)
    summary = {
        "status": "PASS" if not violations else "FAIL",
        "definition_of_done_passed": not violations,
        "generated_at": datetime.now(UTC).isoformat(),
        "documents": [str(path) for path in doc_paths],
        "doc_count": len(doc_paths),
        "preflight": pre,
        "redaction_violations": violations,
        "claim_boundary": "Documentation/reproducibility pack for controlled lab only; public docs do not include private replay payloads.",
        "next_sprint": "Sprint 12 - Final Release Gate",
    }
    write_json(OUT / "sprint11_docs_pack.summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
