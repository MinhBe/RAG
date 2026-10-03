from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUT = Path("artifacts/vaccine_acceptance_seal")
SUMMARY = OUT / "sprint13_acceptance_seal.summary.json"
MANIFEST = OUT / "release_integrity_manifest.jsonl"
CHECKLIST = Path("docs/vaccine_lab/ACCEPTANCE_CHECKLIST.md")

FILES_TO_SEAL = [
    Path("scripts/run_vaccine_full_release_gate.py"),
    Path("scripts/run_vaccine_gate.py"),
    Path("scripts/run_vaccine_sprints_2_3_4.py"),
    Path("scripts/run_vaccine_sprints_5_6_7.py"),
    Path("scripts/run_vaccine_sprints_8_9_10.py"),
    Path("scripts/run_vaccine_sprint_11_docs_pack.py"),
    Path("docs/vaccine_lab/README.md"),
    Path("docs/vaccine_lab/ARCHITECTURE.md"),
    Path("docs/vaccine_lab/RUNBOOK.md"),
    Path("docs/vaccine_lab/TROUBLESHOOTING.md"),
    Path("docs/vaccine_lab/ARTIFACT_MAP.md"),
    Path("docs/vaccine_lab/CLAIM_BOUNDARY.md"),
    Path("docs/vaccine_lab/REPLAY.md"),
    Path("docs/vaccine_lab/ROLLBACK.md"),
    Path("docs/vaccine_lab/NEW_CHAT_HANDOVER.md"),
    Path("artifacts/vaccine_release/final_release_gate.summary.json"),
    Path("artifacts/vaccine_sprint_11/sprint11_docs_pack.summary.json"),
]

CHECKPOINTS = [
    Path(r"C:\Users\Admin\Downloads\Knowleage\Model Setup\43_VACCINE_SPRINT_12_FINAL_RELEASE_PASS_20261004.zip"),
]

FORBIDDEN_PUBLIC_KEYS = {"payload", "generated_payload", "true_expr", "false_expr", "raw_payload"}
PUBLIC_ROOTS = [
    Path("docs/vaccine_lab"),
    Path("artifacts/vaccine_acceptance_seal"),
    Path("artifacts/vaccine_release"),
    Path("artifacts/vaccine_sprint_11"),
]


def run(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    return {
        "args": args,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def git_status_lines() -> list[str]:
    proc = subprocess.run(["git", "status", "--short"], text=True, capture_output=True, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def public_redaction_scan() -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for root in PUBLIC_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".md", ".csv", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for key in FORBIDDEN_PUBLIC_KEYS:
                if f'"{key}"' in text or f"{key}:" in text:
                    violations.append({"path": str(path), "key": key})
    return violations


def build_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in FILES_TO_SEAL + CHECKPOINTS:
        rows.append({
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() else None,
            "kind": "checkpoint" if path in CHECKPOINTS else "repo_artifact",
        })
    write_jsonl(MANIFEST, rows)
    return rows


def build_checklist(manifest_rows: list[dict[str, Any]], final_gate: dict[str, Any]) -> None:
    missing = [row for row in manifest_rows if not row["exists"]]
    content = f"""# Vaccine Lab Acceptance Checklist

Generated: {datetime.now(UTC).isoformat()}

## Release command

```powershell
.\\hermes.cmd vaccine-full-gate
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
{{
  "passed": {str(final_gate.get("passed", False)).lower()},
  "returncode": {final_gate.get("returncode")}
}}
```

## Integrity manifest

Manifest path:

```text
{MANIFEST}
```

Manifest rows: {len(manifest_rows)}
Missing rows: {len(missing)}

## Claim boundary

Controlled lab artifacts only. This is not a production WAF deployment, not broad SQLi protection, and not a claim that vendor full raw SeqGAN self-generated all accepted samples.
"""
    CHECKLIST.write_text(content, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    final_gate = run(["cmd", "/c", "hermes.cmd", "vaccine-full-gate"])
    manifest_rows = build_manifest()
    build_checklist(manifest_rows, final_gate)
    # Rebuild manifest after checklist is created.
    checklist_row = {
        "path": str(CHECKLIST),
        "exists": CHECKLIST.exists(),
        "size_bytes": CHECKLIST.stat().st_size if CHECKLIST.exists() else None,
        "sha256": sha256_file(CHECKLIST) if CHECKLIST.exists() else None,
        "kind": "repo_artifact",
    }
    manifest_rows.append(checklist_row)
    write_jsonl(MANIFEST, manifest_rows)
    redaction_violations = public_redaction_scan()
    missing = [row for row in manifest_rows if not row["exists"]]
    git_lines = git_status_lines()
    expected_dirty_prefixes = {
        "?? artifacts/vaccine_acceptance_seal/",
        "?? docs/vaccine_lab/ACCEPTANCE_CHECKLIST.md",
    }
    unexpected_git = [line for line in git_lines if not any(line.startswith(prefix) for prefix in expected_dirty_prefixes)]
    gates = [
        {"name": "final_release_gate_pass", "passed": final_gate["passed"], "evidence": final_gate},
        {"name": "manifest_complete", "passed": not missing and len(manifest_rows) >= 10, "evidence": {"rows": len(manifest_rows), "missing": missing}},
        {"name": "public_redaction_clean", "passed": not redaction_violations, "evidence": {"violations": redaction_violations}},
        {"name": "acceptance_checklist_exists", "passed": CHECKLIST.exists(), "evidence": {"path": str(CHECKLIST)}},
        {"name": "git_only_expected_acceptance_outputs", "passed": not unexpected_git, "evidence": {"git_status": git_lines, "unexpected": unexpected_git}},
    ]
    summary = {
        "status": "PASS" if all(g["passed"] for g in gates) else "FAIL",
        "definition_of_done_passed": all(g["passed"] for g in gates),
        "generated_at": datetime.now(UTC).isoformat(),
        "claim_boundary": "Post-release acceptance seal for controlled lab artifacts only; no production deployment claim.",
        "manifest": str(MANIFEST),
        "acceptance_checklist": str(CHECKLIST),
        "gates": gates,
        "failed_gates": [g["name"] for g in gates if not g["passed"]],
        "passed_gates": [g["name"] for g in gates if g["passed"]],
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
