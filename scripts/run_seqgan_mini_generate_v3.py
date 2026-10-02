from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARCHIVE_ATTACK_SAMPLES = "Dataset/B_attack_samples/attack_samples_all.csv"
DEFAULT_ARCHIVE = Path("training/seqgan/data/raw/SQLGAN_PostgreSQL_Boolean_Attack_Structure_Corpus_V3.zip")
DEFAULT_TRAIN = Path("training/seqgan/data/processed/v3/splits/train.jsonl")
DEFAULT_OUTPUT_DIR = Path("training/seqgan/data/processed/v3/generated/latest")
PAYLOAD_COLUMNS = ("validation_payload", "payload_normalized", "payload_decoded", "raw_payload")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"no rows loaded from {path}")
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


def static_valid(payload: str) -> bool:
    if len(payload) > 256 or not payload.strip():
        return False
    lower = payload.lower()
    banned = ("http://", "https://", "curl", "wget", "powershell", "cmd.exe", ";", "--", "/*")
    if any(token in lower for token in banned):
        return False
    return payload.count("'") % 2 == 0 and payload.count("(") == payload.count(")")


def learn_policy(train_rows: list[dict[str, Any]], archive_rows: dict[str, dict[str, str]]) -> dict[str, Any]:
    modules = Counter()
    roots = Counter()
    cells = Counter()
    truths = Counter()
    nums = Counter()
    for row in train_rows:
        sample_id = row["sample_id"]
        src = archive_rows[sample_id]
        modules[src["module_id"]] += 1
        roots[src["root_grammar_id"]] += 1
        cells[src["structure_cell_id"]] += 1
        truths[src["expected_truth"]] += 1
        for token in re.findall(r"\b\d{1,6}\b", payload_from_row(src)):
            nums[int(token)] += 1
    return {
        "modules": modules,
        "roots": roots,
        "cells": cells,
        "truths": truths,
        "numbers": nums,
    }


def weighted_choice(rng: random.Random, counter: Counter) -> Any:
    items = list(counter.items())
    total = sum(int(v) for _, v in items)
    pick = rng.randint(1, max(total, 1))
    acc = 0
    for item, weight in items:
        acc += int(weight)
        if pick <= acc:
            return item
    return items[-1][0]


def generate_payload(rng: random.Random, expected_truth: str, number_pool: list[int]) -> str:
    a = rng.choice(number_pool) if number_pool else rng.randint(100, 9999)
    b = a if expected_truth == "TRUE" else a + rng.randint(1, 9)
    template = rng.choice(["eq", "neq", "lt", "gt", "between", "paren_eq"])
    if template == "eq":
        return f"{a} = {b}"
    if template == "neq":
        return f"{a} <> {a + rng.randint(1, 9) if expected_truth == 'TRUE' else a}"
    if template == "lt":
        return f"{a} < {a + 1 if expected_truth == 'TRUE' else a}"
    if template == "gt":
        return f"{a} > {a - 1 if expected_truth == 'TRUE' else a}"
    if template == "between":
        if expected_truth == "TRUE":
            return f"{a} BETWEEN {a - 1} AND {a + 1}"
        return f"{a} BETWEEN {a + 1} AND {a + 9}"
    return f"({a} = {b})"


def run_generation(args: argparse.Namespace) -> dict[str, Any]:
    rng = random.Random(args.seed)
    train_rows = load_jsonl(args.train, args.train_limit)
    archive_rows = load_attack_rows(args.archive, {row["sample_id"] for row in train_rows})
    policy = learn_policy(train_rows, archive_rows)
    number_pool = list(policy["numbers"].keys())[:5000] or list(range(100, 999))
    run_id = f"SEQGAN-SMOKE-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{args.seed}"
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    attempts = 0
    while len(rows) < args.count and attempts < args.count * 20:
        attempts += 1
        expected_truth = weighted_choice(rng, policy["truths"])
        payload = generate_payload(rng, expected_truth, number_pool)
        fp = sha256_text(payload)
        if fp in seen or not static_valid(payload):
            continue
        seen.add(fp)
        idx = len(rows)
        rows.append({
            "sample_id": f"GEN-SMOKE-{idx:06d}",
            "split": "generated",
            "generator_run_id": run_id,
            "generator_kind": "seqgan_small_smoke_statistical_policy",
            "generator_version": "seqgan-smoke-v0.1",
            "model_version": "mle-policy-1epoch-standardlib",
            "source_train_rows": len(train_rows),
            "source_archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
            "candidate_fingerprint": fp,
            "generated_payload": payload,
            "expected_truth": expected_truth,
            "module_id": "Y1_seqgan_generated",
            "y_level": "Y1",
            "root_grammar_id": str(weighted_choice(rng, policy["roots"])),
            "structure_cell_id": f"SEQGAN_SMOKE_CELL_{idx % 32:02d}",
            "boolean_pair_id": f"SEQGAN_SMOKE_PAIR_{idx:06d}",
            "contract_valid": True,
            "static_validator": "hermes_static_boolean_smoke_v1",
            "runtime_claim_allowed": False,
            "postgres_parse_status": "not_run",
            "postgres_runtime_status": "not_run",
            "truth_oracle_status": "not_run",
            "payload_export_policy": "local_runtime_only_gitignored",
        })
    if len(rows) < args.count:
        raise RuntimeError(f"generated only {len(rows)} candidates after {attempts} attempts")
    candidates = out_dir / "generated_candidates.local.jsonl"
    metadata = out_dir / "generated_candidates.metadata.jsonl"
    with candidates.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with metadata.open("w", encoding="utf-8") as handle:
        for row in rows:
            redacted = {k: v for k, v in row.items() if k != "generated_payload"}
            redacted["payload_exported"] = False
            handle.write(json.dumps(redacted, sort_keys=True) + "\n")
    manifest = {
        "status": "ok",
        "run_id": run_id,
        "generator_kind": "seqgan_small_smoke_statistical_policy",
        "generator_version": "seqgan-smoke-v0.1",
        "note": "Fast generated-candidate lane for Hermes Demo B. It is a small SeqGAN-style smoke generator, not the full historical PyTorch V3 trainer.",
        "created_at": datetime.now(UTC).isoformat(),
        "seed": args.seed,
        "requested": args.count,
        "generated": len(rows),
        "attempts": attempts,
        "unique_fingerprints": len(seen),
        "source_train_rows": len(train_rows),
        "payload_exported_in_manifest": False,
        "local_candidates": str(candidates),
        "metadata": str(metadata),
    }
    (out_dir / "generator_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a fast small SeqGAN-style generated candidate lane for Hermes Demo B.")
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE, type=Path)
    parser.add_argument("--train", default=DEFAULT_TRAIN, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
    parser.add_argument("--count", default=128, type=int)
    parser.add_argument("--train-limit", default=2048, type=int)
    parser.add_argument("--seed", default=73, type=int)
    return parser.parse_args()


if __name__ == "__main__":
    run_generation(parse_args())
