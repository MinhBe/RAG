from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paramiko

DEFAULT_CANDIDATES = Path("training/seqgan/data/processed/v3/generated/latest/generated_candidates.local.jsonl")
DEFAULT_OUTPUT = Path("artifacts/boolean_vaccine/generated_acceptance.redacted.jsonl")
PRIVATE_OUTPUT = Path("artifacts/boolean_vaccine/private/generated_acceptance.local.jsonl")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def load_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"no candidates loaded from {path}")
    return rows


def connect(host: str, user: str, key: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    return client


def run_remote_python(client: paramiko.SSHClient, code: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command("python3 -", get_pty=False)
    stdin.write(code)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out, err


def probe_payload(client: paramiko.SSHClient, probe_id: str, payload: str) -> dict[str, Any]:
    encoded_expr = urllib.parse.quote(payload, safe="")
    encoded_probe = urllib.parse.quote(probe_id, safe="")
    code = f'''
import json, os, time, urllib.request, urllib.error
probe_id = {probe_id!r}
url = 'http://127.0.0.1:18080/bool_oracle?probe_id=' + {encoded_probe!r} + '&expr=' + {encoded_expr!r}
access_log = '/var/log/apache2/hermes_lab_access.log'
audit_log = '/var/log/apache2/modsec_audit.log'
def token_count(path, token):
    try:
        needle = token.encode('utf-8')
        with open(path, 'rb') as handle:
            return sum(1 for line in handle if needle in line)
    except OSError:
        return 0
def size(path):
    try: return os.path.getsize(path)
    except OSError: return 0
before_access = token_count(access_log, probe_id)
before_audit = size(audit_log)
status_code = 0
body = ''
error = ''
try:
    req = urllib.request.Request(url, headers={{'User-Agent': 'Hermes-Generated-Boolean-Oracle-Probe/1.0'}})
    with urllib.request.urlopen(req, timeout=8) as response:
        status_code = response.getcode()
        body = response.read(2048).decode('utf-8', errors='replace')
except urllib.error.HTTPError as exc:
    status_code = exc.code
    error = 'HTTPError'
    try: body = exc.read(512).decode('utf-8', errors='replace')
    except Exception: body = ''
except Exception as exc:
    error = type(exc).__name__
time.sleep(0.05)
after_access = token_count(access_log, probe_id)
after_audit = size(audit_log)
parsed = {{}}
try:
    parsed = json.loads(body) if body else {{}}
except Exception:
    parsed = {{}}
print(json.dumps({{
    'probe_id': probe_id,
    'http_status': status_code,
    'backend_reached': bool(parsed.get('backend_reached')),
    'observed_truth': parsed.get('observed_truth', ''),
    'backend_error': parsed.get('error', ''),
    'postgres_status': parsed.get('postgres_status', ''),
    'waf_access_logged': after_access > before_access,
    'waf_audit_logged': after_audit > before_audit,
    'waf_audit_delta_bytes': max(0, after_audit - before_audit),
    'error': error,
}}, sort_keys=True))
'''
    status, out, err = run_remote_python(client, code)
    if status != 0:
        return {"probe_id": probe_id, "http_status": 0, "backend_reached": False, "error": (err or out)[:500]}
    return json.loads(out)


def classify_acceptance(candidate: dict[str, Any], obs: dict[str, Any]) -> tuple[bool, str]:
    expected = str(candidate.get("expected_truth", "")).upper()
    if obs.get("http_status") != 200:
        return False, "blocked_or_http_error"
    if not obs.get("backend_reached"):
        return False, "backend_not_reached"
    if obs.get("observed_truth") != expected:
        return False, "oracle_mismatch"
    if not obs.get("waf_access_logged"):
        return False, "waf_access_not_logged"
    return True, "accepted"


def public_row(candidate: dict[str, Any], obs: dict[str, Any], accepted: bool, reason: str) -> dict[str, Any]:
    payload = str(candidate.get("generated_payload", ""))
    return {
        "sample_id": candidate.get("sample_id"),
        "generator_run_id": candidate.get("generator_run_id"),
        "generator_kind": candidate.get("generator_kind"),
        "module_id": candidate.get("module_id"),
        "y_level": candidate.get("y_level"),
        "root_grammar_id": candidate.get("root_grammar_id"),
        "structure_cell_id": candidate.get("structure_cell_id"),
        "expected_truth": candidate.get("expected_truth"),
        "payload_sha256": sha256_text(payload),
        "payload_redacted": True,
        "payload_exported": False,
        "http_status": obs.get("http_status"),
        "waf_access_logged": bool(obs.get("waf_access_logged")),
        "waf_audit_logged": bool(obs.get("waf_audit_logged")),
        "backend_reached": bool(obs.get("backend_reached")),
        "observed_truth": obs.get("observed_truth"),
        "postgres_status": obs.get("postgres_status"),
        "accepted": accepted,
        "rejection_reason": reason if not accepted else "",
    }


def private_row(candidate: dict[str, Any], public: dict[str, Any]) -> dict[str, Any]:
    row = dict(public)
    row["generated_payload"] = candidate.get("generated_payload")
    return row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay generated Boolean candidates through WAF + backend oracle.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates, args.limit)
    client = connect(args.host, args.user, args.key)
    run_id = datetime.now(UTC).strftime("BOOL-GEN-ORACLE-%Y%m%dT%H%M%SZ")
    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    try:
        for idx, candidate in enumerate(candidates):
            probe_id = f"{run_id}-{idx:04d}"
            payload = str(candidate.get("generated_payload", ""))
            obs = probe_payload(client, probe_id, payload)
            accepted, reason = classify_acceptance(candidate, obs)
            pub = public_row(candidate, obs, accepted, reason)
            public_rows.append(pub)
            private_rows.append(private_row(candidate, pub))
    finally:
        client.close()

    write_jsonl(args.output, public_rows)
    write_jsonl(PRIVATE_OUTPUT, private_rows)
    accepted_rows = [row for row in public_rows if row["accepted"]]
    by_module = Counter(str(row.get("module_id")) for row in accepted_rows)
    summary = {
        "status": "ok" if len(accepted_rows) >= args.limit else "partial",
        "run_id": run_id,
        "target": args.limit,
        "tested": len(public_rows),
        "accepted": len(accepted_rows),
        "waf_access_logged": sum(1 for row in public_rows if row["waf_access_logged"]),
        "waf_audit_logged": sum(1 for row in public_rows if row["waf_audit_logged"]),
        "backend_reached": sum(1 for row in public_rows if row["backend_reached"]),
        "oracle_matched_accepted": len(accepted_rows),
        "payloads_redacted_in_public": True,
        "public_output": str(args.output),
        "private_output": str(PRIVATE_OUTPUT),
        "accepted_by_module": dict(sorted(by_module.items())),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

