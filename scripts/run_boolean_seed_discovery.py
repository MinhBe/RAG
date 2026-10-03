from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paramiko

PRIVATE_DIR = Path("artifacts/boolean_vaccine/private")
PUBLIC_DIR = Path("artifacts/boolean_vaccine")


@dataclass(frozen=True)
class SeedPair:
    seed_id: str
    family: str
    grammar_shape: str
    true_expr: str
    false_expr: str
    features: dict[str, Any]


SEED_POOL = [
    SeedPair("BOOL-SEED-001", "numeric_equality", "number equality comparison", "781 = 781", "781 = 782", {"operator_family": "equality", "has_parentheses": False}),
    SeedPair("BOOL-SEED-002", "numeric_inequality", "number inequality comparison", "782 <> 783", "782 <> 782", {"operator_family": "inequality", "has_parentheses": False}),
    SeedPair("BOOL-SEED-003", "ordered_less_than", "ordered less-than comparison", "17 < 18", "18 < 17", {"operator_family": "ordering", "has_parentheses": False}),
    SeedPair("BOOL-SEED-004", "parenthesized_arithmetic", "parenthesized arithmetic comparison", "(31 + 1) = 32", "(31 + 1) = 33", {"operator_family": "arithmetic_equality", "has_parentheses": True}),
    SeedPair("BOOL-SEED-005", "between_range", "range predicate comparison", "20 BETWEEN 19 AND 21", "20 BETWEEN 21 AND 29", {"operator_family": "range", "has_parentheses": False}),
    SeedPair("BOOL-SEED-006", "multiplicative_arithmetic", "multiplicative arithmetic comparison", "7 * 6 = 42", "7 * 6 = 43", {"operator_family": "arithmetic_equality", "has_parentheses": False}),
    SeedPair("BOOL-SEED-007", "decimal_comparison", "decimal comparison", "10.5 > 10.4", "10.5 < 10.4", {"operator_family": "ordering", "has_decimal": True}),
]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


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


def probe_expr(client: paramiko.SSHClient, probe_id: str, expr: str) -> dict[str, Any]:
    encoded_expr = urllib.parse.quote(expr, safe="")
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
    req = urllib.request.Request(url, headers={{'User-Agent': 'Hermes-Boolean-Seed-Probe/1.0'}})
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
time.sleep(0.08)
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


def redacted_seed(seed: SeedPair, true_obs: dict[str, Any], false_obs: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed_id": seed.seed_id,
        "family": seed.family,
        "grammar_shape": seed.grammar_shape,
        "payload_redacted": True,
        "payload_exported": False,
        "true_expr_sha256": sha256_text(seed.true_expr),
        "false_expr_sha256": sha256_text(seed.false_expr),
        "features": seed.features,
        "waf_result": {
            "true_http_status": true_obs.get("http_status"),
            "false_http_status": false_obs.get("http_status"),
            "true_waf_access_logged": bool(true_obs.get("waf_access_logged")),
            "false_waf_access_logged": bool(false_obs.get("waf_access_logged")),
            "true_waf_audit_logged": bool(true_obs.get("waf_audit_logged")),
            "false_waf_audit_logged": bool(false_obs.get("waf_audit_logged")),
        },
        "backend_oracle": {
            "true_observed": true_obs.get("observed_truth"),
            "false_observed": false_obs.get("observed_truth"),
            "true_backend_reached": bool(true_obs.get("backend_reached")),
            "false_backend_reached": bool(false_obs.get("backend_reached")),
            "true_false_distinguishable": true_obs.get("observed_truth") == "TRUE" and false_obs.get("observed_truth") == "FALSE",
        },
        "accepted": is_accepted(true_obs, false_obs),
    }


def private_seed(seed: SeedPair, public: dict[str, Any]) -> dict[str, Any]:
    row = dict(public)
    row["true_expr"] = seed.true_expr
    row["false_expr"] = seed.false_expr
    return row


def is_accepted(true_obs: dict[str, Any], false_obs: dict[str, Any]) -> bool:
    return (
        true_obs.get("http_status") == 200
        and false_obs.get("http_status") == 200
        and true_obs.get("backend_reached") is True
        and false_obs.get("backend_reached") is True
        and true_obs.get("observed_truth") == "TRUE"
        and false_obs.get("observed_truth") == "FALSE"
        and true_obs.get("waf_access_logged") is True
        and false_obs.get("waf_access_logged") is True
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover five controlled Boolean oracle seeds through WAF + backend.")
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    parser.add_argument("--target", type=int, default=5)
    args = parser.parse_args()

    client = connect(args.host, args.user, args.key)
    accepted_public: list[dict[str, Any]] = []
    accepted_private: list[dict[str, Any]] = []
    rejected_public: list[dict[str, Any]] = []
    run_id = datetime.now(UTC).strftime("BOOL-SEED-DISCOVERY-%Y%m%dT%H%M%SZ")
    try:
        for seed in SEED_POOL:
            true_probe = f"{run_id}-{seed.seed_id}-T"
            false_probe = f"{run_id}-{seed.seed_id}-F"
            true_obs = probe_expr(client, true_probe, seed.true_expr)
            false_obs = probe_expr(client, false_probe, seed.false_expr)
            public = redacted_seed(seed, true_obs, false_obs)
            if public["accepted"] and len(accepted_public) < args.target:
                accepted_public.append(public)
                accepted_private.append(private_seed(seed, public))
            else:
                rejected_public.append(public)
            if len(accepted_public) >= args.target:
                break
    finally:
        client.close()

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(PUBLIC_DIR / "boolean_seeds.redacted.jsonl", accepted_public)
    write_jsonl(PRIVATE_DIR / "boolean_seeds.local.jsonl", accepted_private)
    write_jsonl(PUBLIC_DIR / "boolean_seed_rejections.redacted.jsonl", rejected_public)
    summary = {
        "status": "ok" if len(accepted_public) >= args.target else "partial",
        "run_id": run_id,
        "target": args.target,
        "accepted": len(accepted_public),
        "rejected": len(rejected_public),
        "payloads_redacted_in_public": True,
        "private_payload_store": str(PRIVATE_DIR / "boolean_seeds.local.jsonl"),
        "public_seed_store": str(PUBLIC_DIR / "boolean_seeds.redacted.jsonl"),
        "families": [row["family"] for row in accepted_public],
    }
    (PUBLIC_DIR / "boolean_seed_discovery.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

