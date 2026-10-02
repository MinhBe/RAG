from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from typing import Any

import paramiko

ARCHIVE_ATTACK_SAMPLES = "Dataset/B_attack_samples/attack_samples_all.csv"
DEFAULT_ARCHIVE = Path("training/seqgan/data/raw/SQLGAN_PostgreSQL_Boolean_Attack_Structure_Corpus_V3.zip")
DEFAULT_SPLIT = Path("training/seqgan/data/processed/v3/splits/validation.jsonl")
DEFAULT_OUTPUT = Path("training/seqgan/data/processed/v3/runtime/postgres_probe_sample.jsonl")

PAYLOAD_COLUMNS = (
    "validation_payload",
    "payload_normalized",
    "payload_decoded",
    "raw_payload",
)


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


def load_split(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"no split rows loaded from {path}")
    return rows


def load_attack_rows(archive: Path, sample_ids: set[str]) -> dict[str, dict[str, str]]:
    with zipfile.ZipFile(archive) as zf, zf.open(ARCHIVE_ATTACK_SAMPLES) as raw:
        reader = csv.DictReader(raw.read().decode("utf-8-sig").splitlines())
        rows = {row["sample_id"]: row for row in reader if row["sample_id"] in sample_ids}
    missing = sorted(sample_ids - set(rows))
    if missing:
        raise ValueError(f"missing samples in archive: {missing[:5]}")
    return rows


def payload_from_row(row: dict[str, str]) -> str:
    for column in PAYLOAD_COLUMNS:
        value = row.get(column, "").strip()
        if value:
            return value
    raise ValueError(f"no payload column found for {row.get('sample_id')}")


def run_psql(client: paramiko.SSHClient, sql: str) -> tuple[int, str, str]:
    command = "sudo docker exec -i hermes-lab-postgres psql -U hermes_lab -d hermes_lab -A -t -q -v ON_ERROR_STOP=1"
    stdin, stdout, stderr = client.exec_command(command)
    stdin.write(sql)
    stdin.channel.shutdown_write()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error = stderr.read().decode("utf-8", errors="replace").strip()
    status = stdout.channel.recv_exit_status()
    return status, output, error


def probe_samples(
    host: str,
    user: str,
    key: str,
    split_rows: list[dict[str, Any]],
    archive_rows: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    results = []
    try:
        for split_row in split_rows:
            sample_id = split_row["sample_id"]
            archive_row = archive_rows[sample_id]
            expression = payload_from_row(archive_row)
            expected_truth = archive_row["expected_truth"]
            status, output, error = run_psql(client, build_truth_sql(sample_id, expression))
            observed = output.split("|")[-1].strip() if output else ""
            matched = status == 0 and observed == expected_truth
            results.append(
                {
                    "sample_id": sample_id,
                    "split": split_row.get("split", "validation"),
                    "module_id": archive_row["module_id"],
                    "y_level": archive_row["y_level"],
                    "root_grammar_id": archive_row["root_grammar_id"],
                    "structure_cell_id": archive_row["structure_cell_id"],
                    "expected_truth": expected_truth,
                    "observed_truth": observed if status == 0 else "",
                    "postgres_parse_status": "passed" if status == 0 else "failed",
                    "postgres_runtime_status": "passed" if status == 0 else "failed",
                    "truth_oracle_status": "matched" if matched else "mismatched",
                    "runtime_claim_allowed": bool(matched),
                    "error": error[:500] if error else "",
                }
            )
    finally:
        client.close()
    return results


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a limited PostgreSQL truth probe for local SeqGAN V3 samples.")
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE, type=Path)
    parser.add_argument("--split", default=DEFAULT_SPLIT, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--limit", default=16, type=int)
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    split_rows = load_split(args.split, args.limit)
    sample_ids = {row["sample_id"] for row in split_rows}
    archive_rows = load_attack_rows(args.archive, sample_ids)
    results = probe_samples(args.host, args.user, args.key, split_rows, archive_rows)
    write_jsonl(args.output, results)

    total = len(results)
    matched = sum(1 for row in results if row["truth_oracle_status"] == "matched")
    failed = sum(1 for row in results if row["postgres_runtime_status"] == "failed")
    summary = {
        "status": "ok" if failed == 0 else "partial",
        "samples": total,
        "matched": matched,
        "failed": failed,
        "output": str(args.output),
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
