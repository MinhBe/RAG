from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

import paramiko

ARCHIVE_ATTACK_SAMPLES = "Dataset/B_attack_samples/attack_samples_all.csv"
DEFAULT_ARCHIVE = Path("training/seqgan/data/raw/SQLGAN_PostgreSQL_Boolean_Attack_Structure_Corpus_V3.zip")
DEFAULT_SPLIT = Path("training/seqgan/data/processed/v3/splits/validation.jsonl")
DEFAULT_OUTPUT = Path("training/seqgan/data/processed/v3/runtime/waf_probe_sample.jsonl")
PAYLOAD_COLUMNS = ("validation_payload", "payload_normalized", "payload_decoded", "raw_payload")


def load_split(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def run_remote_python(client: paramiko.SSHClient, code: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command("sudo -n python3 -", get_pty=False)
    stdin.write(code)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err


def probe_one(client: paramiko.SSHClient, sample_id: str, payload: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(payload, safe="")
    code = f"""
import json, os, time, urllib.request, urllib.error
sample_id = {sample_id!r}
encoded = {encoded!r}
access_log = '/var/log/apache2/hermes_lab_access.log'
audit_log = '/var/log/apache2/modsec_audit.log'
def size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
def count_token(path, token):
    try:
        needle = token.encode('utf-8')
        with open(path, 'rb') as handle:
            return sum(1 for line in handle if needle in line)
    except OSError:
        return 0
def lines(path):
    try:
        with open(path, 'rb') as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0
before_access = count_token(access_log, sample_id)
before_access_lines = lines(access_log)
before_audit = size(audit_log)
status_code = 0
error = ''
try:
    url = 'http://127.0.0.1:18080/?sample_id=' + urllib.parse.quote(sample_id) + '&candidate=' + encoded
    req = urllib.request.Request(url, headers={{'User-Agent': 'Hermes-Lab-Probe/1.0'}})
    with urllib.request.urlopen(req, timeout=8) as response:
        status_code = response.getcode()
        response.read(256)
except urllib.error.HTTPError as exc:
    status_code = exc.code
    error = str(exc)[:300]
except Exception as exc:
    error = str(exc)[:300]
time.sleep(0.05)
after_access = count_token(access_log, sample_id)
after_access_lines = lines(access_log)
after_audit = size(audit_log)
print(json.dumps({{
    'sample_id': sample_id,
    'http_status': status_code,
    'waf_access_logged': after_access > before_access,
    'waf_access_delta_lines': max(0, after_access_lines - before_access_lines),
    'waf_access_sample_hits_delta': max(0, after_access - before_access),
    'waf_audit_logged': after_audit > before_audit,
    'waf_audit_delta_bytes': max(0, after_audit - before_audit),
    'waf_mode': 'apache_modsecurity_crs_detection_only_audit_on',
    'error': error,
}}, sort_keys=True))
"""
    status, out, err = run_remote_python(client, code)
    if status != 0:
        return {
            "sample_id": sample_id,
            "http_status": 0,
            "waf_access_logged": False,
            "waf_access_delta_lines": 0,
            "waf_audit_logged": False,
            "waf_audit_delta_bytes": 0,
            "waf_mode": "apache_modsecurity_crs_detection_only_audit_on",
            "error": (err or out)[:500],
        }
    return json.loads(out)


def probe_samples(host: str, user: str, key: str, split_rows: list[dict[str, Any]], archive_rows: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    results: list[dict[str, Any]] = []
    try:
        for split_row in split_rows:
            sample_id = split_row["sample_id"]
            archive_row = archive_rows[sample_id]
            observation = probe_one(client, sample_id, payload_from_row(archive_row))
            observation.update(
                {
                    "split": split_row.get("split", "validation"),
                    "module_id": archive_row["module_id"],
                    "y_level": archive_row["y_level"],
                    "root_grammar_id": archive_row["root_grammar_id"],
                    "structure_cell_id": archive_row["structure_cell_id"],
                    "expected_truth": archive_row["expected_truth"],
                }
            )
            results.append(observation)
    finally:
        client.close()
    return results


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a limited WAF/CRS HTTP telemetry probe for local SeqGAN V3 samples.")
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
    summary = {
        "status": "ok" if all(row.get("waf_access_logged") for row in results) else "partial",
        "samples": len(results),
        "http_ok": sum(1 for row in results if int(row.get("http_status", 0)) < 500 and int(row.get("http_status", 0)) > 0),
        "waf_access_logged": sum(1 for row in results if row.get("waf_access_logged")),
        "waf_audit_logged": sum(1 for row in results if row.get("waf_audit_logged")),
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
