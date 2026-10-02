from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path
from typing import Any

import paramiko

DEFAULT_CANDIDATES = Path("training/seqgan/data/processed/v3/generated/latest/generated_candidates.local.jsonl")
DEFAULT_OUTPUT = Path("training/seqgan/data/processed/v3/runtime/generated_waf_probe.jsonl")


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
    try: return os.path.getsize(path)
    except OSError: return 0
def count_token(path, token):
    try:
        needle = token.encode('utf-8')
        with open(path, 'rb') as handle:
            return sum(1 for line in handle if needle in line)
    except OSError:
        return 0
before_access = count_token(access_log, sample_id)
before_audit = size(audit_log)
status_code = 0
error = ''
try:
    url = 'http://127.0.0.1:18080/?sample_id=' + urllib.parse.quote(sample_id) + '&candidate=' + encoded
    req = urllib.request.Request(url, headers={{'User-Agent': 'Hermes-Generated-Probe/1.0'}})
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
after_audit = size(audit_log)
print(json.dumps({{
    'sample_id': sample_id,
    'http_status': status_code,
    'waf_access_logged': after_access > before_access,
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
            "waf_audit_logged": False,
            "waf_mode": "apache_modsecurity_crs_detection_only_audit_on",
            "error": (err or out)[:500],
        }
    return json.loads(out)


def probe(host: str, user: str, key: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    rows: list[dict[str, Any]] = []
    try:
        for candidate in candidates:
            observation = probe_one(client, str(candidate["sample_id"]), str(candidate["generated_payload"]))
            observation.update({
                "split": "generated",
                "generator_run_id": candidate.get("generator_run_id"),
                "generator_kind": candidate.get("generator_kind"),
                "module_id": candidate["module_id"],
                "y_level": candidate["y_level"],
                "root_grammar_id": candidate["root_grammar_id"],
                "structure_cell_id": candidate["structure_cell_id"],
                "expected_truth": candidate["expected_truth"],
                "payload_exported": False,
            })
            rows.append(observation)
    finally:
        client.close()
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WAF/CRS probe for generated SeqGAN smoke candidates.")
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
        "status": "ok" if all(row.get("waf_access_logged") and row.get("waf_audit_logged") for row in rows) else "partial",
        "samples": len(rows),
        "http_ok": sum(1 for row in rows if int(row.get("http_status", 0)) > 0 and int(row.get("http_status", 0)) < 500),
        "waf_access_logged": sum(1 for row in rows if row.get("waf_access_logged")),
        "waf_audit_logged": sum(1 for row in rows if row.get("waf_audit_logged")),
        "generated": True,
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
