from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path.cwd().resolve()
OUT = Path("artifacts/vaccine_restore_drill")
WORKSPACE_ROOT = (ROOT / OUT / "workspace").resolve()
CLONE_DIR = (WORKSPACE_ROOT / "hermes-clean-clone").resolve()
SUMMARY = OUT / "sprint14_restore_drill.summary.json"
DOC = Path("docs/vaccine_lab/RESTORE_DRILL.md")

REQUIRED_COPY_PATHS = [
    Path("artifacts/boolean_vaccine"),
    Path("artifacts/vaccine_sprints_2_3_4"),
    Path("artifacts/vaccine_sprints_5_6_7"),
    Path("artifacts/vaccine_sprints_8_9_10"),
    Path("artifacts/vaccine_sprint_11"),
    Path("artifacts/vaccine_release"),
    Path("artifacts/vaccine_acceptance_seal"),
]

PUBLIC_ARTIFACTS = [
    Path("docs/vaccine_lab"),
    Path("artifacts/vaccine_restore_drill"),
]

RAW_KEYS = {"payload", "generated_payload", "true_expr", "false_expr"}


def run(args: list[str], cwd: Path | None = None, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "args": args,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def copy_tree(src: Path, dst: Path) -> dict[str, Any]:
    if not src.exists():
        return {"source": str(src), "destination": str(dst), "exists": False, "copied": False}
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    file_count = sum(1 for p in dst.rglob("*") if p.is_file())
    return {"source": str(src), "destination": str(dst), "exists": True, "copied": True, "file_count": file_count}


def scan_redaction(paths: list[Path]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for base in paths:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".md", ".csv"}:
                continue
            # Explicitly skip the private replay tree inside runtime-only restored workspace.
            parts = {part.lower() for part in path.parts}
            if "private" in parts or "workspace" in parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(f'"{key}"' in text for key in RAW_KEYS):
                violations.append({"path": str(path), "reason": "raw_payload_key_present"})
    return violations


def build_restore_doc(summary: dict[str, Any]) -> None:
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(
        "# Vaccine Restore Drill\n\n"
        "This document records the post-release restore-on-clean-workspace drill.\n\n"
        "## Restore model\n\n"
        "A clean Git clone alone is not sufficient because private replay artifacts are intentionally not committed. "
        "The valid restore model is:\n\n"
        "```text\n"
        "git clone + local private/checkpoint artifacts -> restored workspace -> hermes vaccine-full-gate PASS\n"
        "```\n\n"
        "## Result\n\n"
        f"- Status: `{summary.get('status')}`\n"
        f"- Definition of Done: `{summary.get('definition_of_done_passed')}`\n"
        f"- Clean clone gate: `{summary.get('clean_clone_gate', {}).get('passed')}`\n"
        f"- Redaction violations: `{len(summary.get('redaction_violations', []))}`\n\n"
        "## Manual verification\n\n"
        "1. Open the checkpoint directory for Sprint 14.\n"
        "2. Inspect `sprint14_restore_drill.summary.json`.\n"
        "3. Confirm `clean_clone_gate.passed = true`.\n"
        "4. Confirm `public_redaction_clean = true`.\n"
        "5. Re-run `hermes vaccine-full-gate` from the main repo.\n\n"
        "## Boundary\n\n"
        "Controlled lab reproducibility only. This is not a production WAF deployment or broad SQLi protection claim.\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pre_gate = run(["cmd", "/c", "hermes.cmd", "vaccine-full-gate"], cwd=ROOT, timeout=240)
    source_status = run(["git", "status", "--short"], cwd=ROOT)

    if WORKSPACE_ROOT.exists():
        shutil.rmtree(WORKSPACE_ROOT)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    clone = run(["git", "clone", str(ROOT), str(CLONE_DIR)], cwd=WORKSPACE_ROOT, timeout=120)
    copied = []
    if clone["passed"]:
        for rel in REQUIRED_COPY_PATHS:
            copied.append(copy_tree(ROOT / rel, CLONE_DIR / rel))

    clean_gate = {"passed": False, "skipped": True, "reason": "clone_failed"}
    clean_git_status = {"passed": False, "stdout_tail": ""}
    if clone["passed"]:
        clean_gate = run(["cmd", "/c", "hermes.cmd", "vaccine-full-gate"], cwd=CLONE_DIR, timeout=300)
        clean_git_status = run(["git", "status", "--short"], cwd=CLONE_DIR)

    redaction_violations = scan_redaction(PUBLIC_ARTIFACTS)
    gates = [
        {"name": "source_final_gate_pass", "passed": pre_gate["passed"], "evidence": pre_gate},
        {"name": "local_clone_created", "passed": clone["passed"], "evidence": clone},
        {"name": "private_artifact_handoff_copied", "passed": bool(copied) and all(row.get("copied") for row in copied), "evidence": {"copied": copied}},
        {"name": "clean_workspace_final_gate_pass", "passed": clean_gate.get("passed") is True, "evidence": clean_gate},
        {"name": "public_redaction_clean", "passed": not redaction_violations, "evidence": {"violations": redaction_violations}},
    ]
    status = "PASS" if all(g["passed"] for g in gates) else "FAIL"
    summary = {
        "status": status,
        "definition_of_done_passed": status == "PASS",
        "generated_at": datetime.now(UTC).isoformat(),
        "claim_boundary": "Restore-on-clean-workspace drill for controlled lab artifacts only; private replay artifacts remain local and are not public.",
        "source_git_status_before": source_status.get("stdout_tail", ""),
        "clone_path": str(CLONE_DIR),
        "source_final_gate": pre_gate,
        "clone_result": clone,
        "artifact_handoff": copied,
        "clean_clone_gate": clean_gate,
        "clean_clone_git_status": clean_git_status.get("stdout_tail", ""),
        "redaction_violations": redaction_violations,
        "public_redaction_clean": not redaction_violations,
        "gates": gates,
        "failed_gates": [g["name"] for g in gates if not g["passed"]],
        "next_boundary": "After this drill, further work should be a separate production design or an external manual review, not more lab sprinting.",
    }
    write_json(SUMMARY, summary)
    build_restore_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
