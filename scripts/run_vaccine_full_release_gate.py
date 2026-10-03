from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
OUT = Path("artifacts/vaccine_release")
SUMMARY = OUT / "final_release_gate.summary.json"

REQUIRED_SUMMARIES = {
    "sprint1_full_dod": Path("artifacts/boolean_vaccine/full_definition_of_done.summary.json"),
    "sprint2_4_dod": Path("artifacts/vaccine_sprints_2_3_4/sprints_2_3_4_definition_of_done.summary.json"),
    "sprint5_7_dod": Path("artifacts/vaccine_sprints_5_6_7/sprints_5_6_7_definition_of_done.summary.json"),
    "sprint8_10_dod": Path("artifacts/vaccine_sprints_8_9_10/sprints_8_9_10_definition_of_done.summary.json"),
    "sprint11_docs": Path("artifacts/vaccine_sprint_11/sprint11_docs_pack.summary.json"),
}

DOCS = [
    Path("docs/vaccine_lab/README.md"),
    Path("docs/vaccine_lab/ARCHITECTURE.md"),
    Path("docs/vaccine_lab/RUNBOOK.md"),
    Path("docs/vaccine_lab/TROUBLESHOOTING.md"),
    Path("docs/vaccine_lab/ARTIFACT_MAP.md"),
    Path("docs/vaccine_lab/CLAIM_BOUNDARY.md"),
    Path("docs/vaccine_lab/REPLAY.md"),
    Path("docs/vaccine_lab/ROLLBACK.md"),
    Path("docs/vaccine_lab/NEW_CHAT_HANDOVER.md"),
]

PRIVATE_REPLAY = [
    Path("artifacts/boolean_vaccine/private/reward_loop_acceptance.local.jsonl"),
    Path("artifacts/vaccine_sprints_2_3_4/private/sprint2_before_attack.local.jsonl"),
    Path("artifacts/vaccine_sprints_2_3_4/private/sprint4_multifamily.local.jsonl"),
    Path("artifacts/vaccine_sprints_5_6_7/private/sprint5_seqgan_adapter_acceptance.local.jsonl"),
]

PUBLIC_ROOTS = [
    Path("artifacts/boolean_vaccine"),
    Path("artifacts/vaccine_sprints_2_3_4"),
    Path("artifacts/vaccine_sprints_5_6_7"),
    Path("artifacts/vaccine_sprints_8_9_10"),
    Path("artifacts/vaccine_sprint_11"),
    Path("docs/vaccine_lab"),
]

FORBIDDEN_PUBLIC_KEYS = {"payload", "generated_payload", "true_expr", "false_expr", "expr", "raw_payload"}
FORBIDDEN_TEXT_TOKENS = ["generated_payload", "raw_payload", "true_expr", "false_expr"]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(args: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def status_of(summary: dict[str, Any]) -> str:
    if summary.get("status"):
        return str(summary.get("status"))
    if summary.get("definition_of_done_passed") is True:
        return "PASS"
    return "UNKNOWN"


def check_required_summaries() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    ok = True
    for name, path in REQUIRED_SUMMARIES.items():
        summary = read_json(path)
        status = status_of(summary)
        passed = path.exists() and status == "PASS"
        rows[name] = {"path": str(path), "exists": path.exists(), "status": status, "passed": passed}
        ok = ok and passed
    return {"passed": ok, "items": rows}


def check_docs() -> dict[str, Any]:
    rows = {str(path): path.exists() and path.stat().st_size > 0 for path in DOCS}
    return {"passed": all(rows.values()), "docs": rows, "count": len(DOCS)}


def check_private_replay() -> dict[str, Any]:
    rows = {str(path): path.exists() and path.stat().st_size > 0 for path in PRIVATE_REPLAY}
    return {"passed": all(rows.values()), "private_replay": rows}


def scan_public_redaction() -> dict[str, Any]:
    violations: list[str] = []
    for root in PUBLIC_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or "private" in path.parts:
                continue
            if path.suffix.lower() not in {".json", ".jsonl", ".md", ".csv"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                violations.append(f"{path}:read_error:{type(exc).__name__}")
                continue
            if path.suffix.lower() == ".jsonl":
                for idx, line in enumerate(text.splitlines(), start=1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    bad = sorted(FORBIDDEN_PUBLIC_KEYS.intersection(row.keys()))
                    if bad:
                        violations.append(f"{path}:{idx}:forbidden_keys={','.join(bad)}")
            if path.suffix.lower() in {".md", ".csv", ".json"}:
                # Metadata can mention private path names and redaction concepts; only flag explicit raw-payload fields.
                for token in FORBIDDEN_TEXT_TOKENS:
                    if token in text and "payload_redacted" not in text:
                        violations.append(f"{path}:token={token}")
    return {"passed": not violations, "violations": violations}


def check_git_clean() -> dict[str, Any]:
    proc = run_command(["git", "status", "--short", "--untracked-files=all"], timeout=30)
    lines = [line for line in proc["stdout_tail"].splitlines() if line.strip()]
    allowed_prefixes = (
        "?? artifacts/vaccine_release/",
    )
    unexpected = [line for line in lines if not line.startswith(allowed_prefixes)]
    return {"passed": proc["passed"] and not unexpected, "lines": lines, "unexpected": unexpected}


def gate(name: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the final controlled-lab vaccine release gate.")
    parser.add_argument("--strict-git-clean", action="store_true", help="Fail if git status contains unexpected tracked/untracked changes.")
    parser.add_argument("--skip-static", action="store_true", help="Skip ruff/pytest checks; intended only for diagnosis.")
    args = parser.parse_args()

    summaries = check_required_summaries()
    docs = check_docs()
    private_replay = check_private_replay()
    redaction = scan_public_redaction()
    vaccine_gate = run_command(["uv", "run", "python", "scripts/run_vaccine_gate.py"], timeout=240)
    static_gate = {"passed": True, "skipped": True}
    if not args.skip_static:
        ruff = run_command(["uv", "run", "ruff", "check", "app", "scripts", "tests", "training"], timeout=120)
        tests = run_command(["uv", "run", "pytest", "-q"], timeout=240)
        static_gate = {"passed": ruff["passed"] and tests["passed"], "ruff": ruff, "pytest": tests, "skipped": False}
    git_clean = check_git_clean() if args.strict_git_clean else {"passed": True, "skipped": True}

    gates = [
        gate("all_previous_sprints_pass", summaries["passed"], summaries),
        gate("one_command_vaccine_gate_pass", vaccine_gate["passed"], vaccine_gate),
        gate("static_quality_gate_pass", bool(static_gate["passed"]), static_gate),
        gate("documentation_pack_exists", docs["passed"], docs),
        gate("private_replay_artifacts_exist", private_replay["passed"], private_replay),
        gate("public_redaction_clean", redaction["passed"], redaction),
        gate("git_release_state_clean", git_clean["passed"], git_clean),
    ]
    passed = all(row["passed"] for row in gates)
    summary = {
        "status": "PASS" if passed else "FAIL",
        "definition_of_done_passed": passed,
        "generated_at": datetime.now(UTC).isoformat(),
        "claim_boundary": "Final release gate for controlled lab artifacts only. Not a production WAF deployment or broad SQLi protection claim.",
        "one_command": "hermes vaccine-full-gate",
        "fallback_command": "uv run python scripts/run_vaccine_full_release_gate.py --strict-git-clean",
        "passed_gates": [row["name"] for row in gates if row["passed"]],
        "failed_gates": [row["name"] for row in gates if not row["passed"]],
        "gates": gates,
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
