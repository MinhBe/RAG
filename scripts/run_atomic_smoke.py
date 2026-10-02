from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paramiko

DEFAULT_OUTPUT = Path("training/seqgan/data/processed/v3/runtime/atomic_smoke.jsonl")

SMOKE_TESTS = [
    {
        "technique_id": "T1059.004",
        "test_name": "What shell is running",
        "atomic_guid": "7b38e5cc-47be-44f0-a425-390305c76c17",
        "command": "echo $0; if env | grep '^SHELL=' >/dev/null; then env | grep '^SHELL='; fi; if printenv SHELL >/dev/null; then printenv SHELL; fi",
    },
    {
        "technique_id": "T1087.001",
        "test_name": "Enumerate users and groups",
        "atomic_guid": "e6f36545-dc1e-47f0-9f48-7f730f54a02e",
        "command": "groups; id",
    },
]


def run_command(client: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    safe_command = "set -eu\n" + command + "\n"
    stdin, stdout, stderr = client.exec_command("bash -s", get_pty=False)
    stdin.write(safe_command)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def run_smoke(host: str, user: str, key: str) -> list[dict[str, Any]]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    rows: list[dict[str, Any]] = []
    try:
        for test in SMOKE_TESTS:
            status, out, err = run_command(client, test["command"])
            rows.append(
                {
                    "technique_id": test["technique_id"],
                    "test_name": test["test_name"],
                    "atomic_guid": test["atomic_guid"],
                    "execution_status": "completed" if status == 0 else "failed",
                    "exit_code": status,
                    "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "stdout_sha256": hashlib.sha256(out.encode("utf-8", errors="replace")).hexdigest(),
                    "stdout_line_count": len([line for line in out.splitlines() if line.strip()]),
                    "stderr_line_count": len([line for line in err.splitlines() if line.strip()]),
                    "raw_output_stored": False,
                    "lab_scope": "local_vm_only",
                    "source_repo_present": True,
                }
            )
    finally:
        client.close()
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal local Atomic Red Team smoke slice and store metadata only.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = run_smoke(args.host, args.user, args.key)
    write_jsonl(args.output, rows)
    completed = sum(1 for row in rows if row["execution_status"] == "completed")
    summary = {"status": "ok" if completed == len(rows) else "partial", "tests": len(rows), "completed": completed, "output": str(args.output)}
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if completed != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
