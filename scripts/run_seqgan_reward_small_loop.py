from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from typing import Any

import paramiko

from app.core.boolean_vaccine import (
    compute_reward,
    extract_grammar_features,
    generate_expr_for_family,
    normalize_expr,
    public_candidate,
    sha256_text,
)

DEFAULT_SEED_GRAMMAR = Path("artifacts/boolean_vaccine/seed_grammar.redacted.jsonl")
DEFAULT_PUBLIC_OUTPUT = Path("artifacts/boolean_vaccine/reward_loop_acceptance.redacted.jsonl")
DEFAULT_PRIVATE_OUTPUT = Path("artifacts/boolean_vaccine/private/reward_loop_acceptance.local.jsonl")
DEFAULT_REJECTIONS = Path("artifacts/boolean_vaccine/reward_loop_rejections.redacted.jsonl")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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
    req = urllib.request.Request(url, headers={{'User-Agent': 'Hermes-SeqGAN-Reward-Loop/1.0'}})
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
time.sleep(0.04)
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


def seed_families(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    seen: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        family = str(row["family"])
        if family not in seen:
            seen[family] = (str(row["seed_id"]), family, str(row.get("grammar_shape", family)))
    return list(seen.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small SeqGAN-style reward loop against the safe Boolean oracle lab.")
    parser.add_argument("--seed-grammar", type=Path, default=DEFAULT_SEED_GRAMMAR)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--private-output", type=Path, default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--rejections-output", type=Path, default=DEFAULT_REJECTIONS)
    parser.add_argument("--target", type=int, default=50)
    parser.add_argument("--seed", type=int, default=404)
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    args = parser.parse_args()
    grammar_rows = load_jsonl(args.seed_grammar)
    families = seed_families(grammar_rows)
    if not families:
        raise ValueError("no seed grammar families available")
    target_per_family = args.target // len(families)
    if target_per_family * len(families) != args.target:
        raise ValueError("target must divide evenly by family count")
    rng = random.Random(args.seed)
    run_id = datetime.now(UTC).strftime("SEQGAN-REWARD-SMALL-%Y%m%dT%H%M%SZ")
    accepted_public: list[dict[str, Any]] = []
    accepted_private: list[dict[str, Any]] = []
    rejected_public: list[dict[str, Any]] = []
    accepted_by_family: Counter[str] = Counter()
    seen_hashes: set[str] = set()
    attempts = 0
    max_attempts = args.target * 30
    client = connect(args.host, args.user, args.key)
    try:
        while len(accepted_public) < args.target and attempts < max_attempts:
            for seed_id, family, grammar_shape in families:
                if accepted_by_family[family] >= target_per_family:
                    continue
                attempts += 1
                expr, expected_truth = generate_expr_for_family(family, attempts, rng)
                features = extract_grammar_features(expr, seed_id=seed_id, family=family)
                payload_hash = sha256_text(normalize_expr(expr))
                duplicate = payload_hash in seen_hashes
                candidate = {
                    "sample_id": f"SRL-{len(accepted_public) + len(rejected_public):06d}",
                    "run_id": run_id,
                    "generator_kind": "seqgan_reward_small_loop_restricted_boolean_v0",
                    "seed_id": seed_id,
                    "family": family,
                    "grammar_shape": grammar_shape,
                    "expected_truth": expected_truth,
                    "generated_payload": expr,
                    "payload_exported": False,
                    **features,
                }
                obs = probe_payload(client, str(candidate["sample_id"]), expr)
                reward = compute_reward(candidate, obs, family_count=accepted_by_family[family], target_per_family=target_per_family, duplicate=duplicate)
                pub = public_candidate(candidate, obs, reward)
                if reward["accepted"]:
                    seen_hashes.add(payload_hash)
                    accepted_by_family[family] += 1
                    accepted_public.append(pub)
                    private = dict(pub)
                    private["generated_payload"] = expr
                    accepted_private.append(private)
                else:
                    rejected_public.append(pub)
                if len(accepted_public) >= args.target:
                    break
    finally:
        client.close()
    write_jsonl(args.public_output, accepted_public)
    write_jsonl(args.private_output, accepted_private)
    write_jsonl(args.rejections_output, rejected_public)
    summary = {
        "status": "ok" if len(accepted_public) >= args.target and min(accepted_by_family.values() or [0]) >= target_per_family else "partial",
        "run_id": run_id,
        "generator_kind": "seqgan_reward_small_loop_restricted_boolean_v0",
        "claim_boundary": "Small reward loop over restricted Boolean grammar lanes; not a claim that raw full SeqGAN alone generated accepted outputs.",
        "target": args.target,
        "target_per_family": target_per_family,
        "accepted": len(accepted_public),
        "rejected": len(rejected_public),
        "attempts": attempts,
        "families": [family for _, family, _ in families],
        "accepted_by_family": dict(sorted(accepted_by_family.items())),
        "min_per_family": min(accepted_by_family.values() or [0]),
        "max_per_family": max(accepted_by_family.values() or [0]),
        "payloads_redacted_in_public": True,
        "private_output": str(args.private_output),
        "public_output": str(args.public_output),
        "rejections_output": str(args.rejections_output),
    }
    args.public_output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

