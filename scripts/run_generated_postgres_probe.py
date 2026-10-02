from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import paramiko

DEFAULT_CANDIDATES = Path("training/seqgan/data/processed/v3/generated/latest/generated_candidates.local.jsonl")
DEFAULT_OUTPUT = Path("training/seqgan/data/processed/v3/runtime/generated_postgres_probe.jsonl")


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_truth_sql(sample_id: str, expression: str) -> str:
    sample_literal = sql_quote(sample_id)
    return f"""
SELECT {sample_literal} AS sample_id,
       CASE
         WHEN ({expression}) IS TRUE THEN 'TRUE'
         WHEN ({expression}) IS FALSE THEN 'FALSE'
         ELSE 'NULL'
       END AS observed_truth;
""".strip() + "\n"


def load_candidates(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"no generated candidates loaded from {path}")
    return rows


def run_psql(client: paramiko.SSHClient, sql: str) -> tuple[int, str, str]:
    command = "sudo docker exec -i hermes-lab-postgres psql -U hermes_lab -d hermes_lab -A -t -q -v ON_ERROR_STOP=1"
    stdin, stdout, stderr = client.exec_command(command)
    stdin.write(sql)
    stdin.channel.shutdown_write()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error = stderr.read().decode("utf-8", errors="replace").strip()
    status = stdout.channel.recv_exit_status()
    return status, output, error


def probe(host: str, user: str, key: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    rows: list[dict[str, Any]] = []
    try:
        for candidate in candidates:
            payload = str(candidate["generated_payload"])
            expected_truth = str(candidate["expected_truth"])
            status, output, error = run_psql(client, build_truth_sql(str(candidate["sample_id"]), payload))
            observed = output.split("|")[-1].strip() if output else ""
            matched = status == 0 and observed == expected_truth
            rows.append({
                "sample_id": candidate["sample_id"],
                "split": "generated",
                "generator_run_id": candidate.get("generator_run_id"),
                "generator_kind": candidate.get("generator_kind"),
                "module_id": candidate["module_id"],
                "y_level": candidate["y_level"],
                "root_grammar_id": candidate["root_grammar_id"],
                "structure_cell_id": candidate["structure_cell_id"],
                "expected_truth": expected_truth,
                "observed_truth": observed if status == 0 else "",
                "postgres_parse_status": "passed" if status == 0 else "failed",
                "postgres_runtime_status": "passed" if status == 0 else "failed",
                "truth_oracle_status": "matched" if matched else "mismatched",
                "runtime_claim_allowed": bool(matched),
                "payload_exported": False,
                "error": error[:500] if error else "",
            })
    finally:
        client.close()
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PostgreSQL truth probe for generated SeqGAN smoke candidates.")
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--limit", default=128, type=int)
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = load_candidates(args.candidates, args.limit)
    rows = probe(args.host, args.user, args.key, candidates)
    write_jsonl(args.output, rows)
    summary = {
        "status": "ok" if all(row["truth_oracle_status"] == "matched" for row in rows) else "partial",
        "samples": len(rows),
        "matched": sum(1 for row in rows if row["truth_oracle_status"] == "matched"),
        "failed": sum(1 for row in rows if row["postgres_runtime_status"] == "failed"),
        "generated": True,
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
