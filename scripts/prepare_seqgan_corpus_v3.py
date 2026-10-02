from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ARCHIVE_DATASET_MANIFEST = "Dataset/dataset_manifest.json"
ARCHIVE_QA_REPORT = "Dataset/QA_REPORT.json"
ARCHIVE_ATTACK_SAMPLES = "Dataset/B_attack_samples/attack_samples_all.csv"
ARCHIVE_STATIC_VALIDATION = "Dataset/E_validation/static_validation_results.csv"
ARCHIVE_SHA256 = "SHA256.txt"

RUNTIME_STATUS_COLUMNS = (
    "postgres_parse_status",
    "postgres_runtime_status",
    "truth_oracle_status",
)


@dataclass(frozen=True)
class SplitRatios:
    train: int = 80
    validation: int = 10
    frozen_test: int = 10

    def validate(self) -> None:
        if self.train <= 0 or self.validation <= 0 or self.frozen_test <= 0:
            raise ValueError("split ratios must be positive")
        if self.train + self.validation + self.frozen_test != 100:
            raise ValueError("split ratios must sum to 100")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_from_zip(zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(zf.read(name).decode("utf-8-sig"))


def verify_declared_checksums(zf: zipfile.ZipFile) -> dict[str, Any]:
    if ARCHIVE_SHA256 not in zf.namelist():
        return {"present": False, "verified": 0, "bad": [], "missing": []}
    verified = 0
    bad: list[str] = []
    missing: list[str] = []
    for line in zf.read(ARCHIVE_SHA256).decode("utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.replace("*", " ").split()
        if len(parts) < 2 or len(parts[0]) != 64:
            continue
        expected, member = parts[0].lower(), parts[-1]
        if member not in zf.namelist():
            missing.append(member)
            continue
        actual = hashlib.sha256(zf.read(member)).hexdigest()
        if actual == expected:
            verified += 1
        else:
            bad.append(member)
    return {"present": True, "verified": verified, "bad": bad, "missing": missing}


def split_name_for_fingerprint(fingerprint: str, ratios: SplitRatios) -> str:
    bucket = int(hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < ratios.train:
        return "train"
    if bucket < ratios.train + ratios.validation:
        return "validation"
    return "frozen_test"


def read_attack_rows(zf: zipfile.ZipFile) -> list[dict[str, str]]:
    with zf.open(ARCHIVE_ATTACK_SAMPLES) as raw:
        text = raw.read().decode("utf-8-sig").splitlines()
    return list(csv.DictReader(text))


def summarize_static_validation(zf: zipfile.ZipFile) -> dict[str, Any]:
    with zf.open(ARCHIVE_STATIC_VALIDATION) as raw:
        rows = list(csv.DictReader(raw.read().decode("utf-8-sig").splitlines()))
    total = len(rows)
    if total == 0:
        raise ValueError("static validation table is empty")
    status_counts = {col: Counter(row[col] for row in rows) for col in RUNTIME_STATUS_COLUMNS}
    return {
        "rows": total,
        "all_contract_valid": all(row["contract_valid"] == "True" for row in rows),
        "all_required_tokens_valid": all(row["required_tokens_valid"] == "True" for row in rows),
        "runtime_status_counts": {key: dict(value) for key, value in status_counts.items()},
        "exploit_confirmed_counts": dict(Counter(row["exploit_confirmed"] for row in rows)),
        "runtime_claim_allowed_counts": dict(Counter(row["runtime_claim_allowed"] for row in rows)),
    }


def build_split(rows: list[dict[str, str]], ratios: SplitRatios) -> dict[str, Any]:
    split_rows: dict[str, list[dict[str, str]]] = {
        "train": [],
        "validation": [],
        "frozen_test": [],
    }
    fingerprint_to_split: dict[str, str] = {}
    for row in rows:
        fingerprint = row["attack_fingerprint"]
        split = split_name_for_fingerprint(fingerprint, ratios)
        fingerprint_to_split[fingerprint] = split
        split_rows[split].append(row)

    fingerprints_by_split: dict[str, set[str]] = defaultdict(set)
    for fingerprint, split in fingerprint_to_split.items():
        fingerprints_by_split[split].add(fingerprint)
    overlaps = {
        "train_validation": sorted(fingerprints_by_split["train"] & fingerprints_by_split["validation"]),
        "train_frozen_test": sorted(fingerprints_by_split["train"] & fingerprints_by_split["frozen_test"]),
        "validation_frozen_test": sorted(fingerprints_by_split["validation"] & fingerprints_by_split["frozen_test"]),
    }

    return {
        "split_rows": split_rows,
        "fingerprint_to_split": fingerprint_to_split,
        "overlaps": overlaps,
    }


def compact_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "sample_id": row["sample_id"],
        "attack_fingerprint": row["attack_fingerprint"],
        "module_id": row["module_id"],
        "y_level": row["y_level"],
        "root_grammar_id": row["root_grammar_id"],
        "structure_cell_id": row["structure_cell_id"],
        "boolean_pair_id": row["boolean_pair_id"],
        "expected_truth": row["expected_truth"],
        "difficulty_level": row["difficulty_level"],
        "contract_valid": row["contract_valid"],
        "postgres_parse_status": row["postgres_parse_status"],
        "postgres_runtime_status": row["postgres_runtime_status"],
        "truth_oracle_status": row["truth_oracle_status"],
        "runtime_claim_allowed": row["runtime_claim_allowed"],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(compact_row(row), sort_keys=True) + "\n")


def prepare_archive(archive: Path, output_dir: Path, ratios: SplitRatios) -> dict[str, Any]:
    ratios.validate()
    archive = archive.resolve()
    if not archive.exists():
        raise FileNotFoundError(archive)

    archive_sha256 = sha256_file(archive)
    created_at = datetime.now(UTC).isoformat()
    with zipfile.ZipFile(archive) as zf:
        required = {
            ARCHIVE_DATASET_MANIFEST,
            ARCHIVE_QA_REPORT,
            ARCHIVE_ATTACK_SAMPLES,
            ARCHIVE_STATIC_VALIDATION,
        }
        missing = sorted(required - set(zf.namelist()))
        if missing:
            raise ValueError(f"archive missing required members: {missing}")
        dataset_manifest = load_json_from_zip(zf, ARCHIVE_DATASET_MANIFEST)
        qa_report = load_json_from_zip(zf, ARCHIVE_QA_REPORT)
        checksum_report = verify_declared_checksums(zf)
        static_summary = summarize_static_validation(zf)
        rows = read_attack_rows(zf)

    if len(rows) != int(dataset_manifest["counts"]["total_samples"]):
        raise ValueError("sample count does not match dataset manifest")
    if checksum_report["bad"] or checksum_report["missing"]:
        raise ValueError(f"checksum verification failed: {checksum_report}")

    split = build_split(rows, ratios)
    if any(split["overlaps"].values()):
        raise ValueError("fingerprint leakage detected across splits")

    splits_dir = output_dir / "splits"
    for name, split_rows in split["split_rows"].items():
        write_jsonl(splits_dir / f"{name}.jsonl", split_rows)

    by_module = Counter(row["module_id"] for row in rows)
    split_counts = {name: len(items) for name, items in split["split_rows"].items()}
    split_by_module = {
        name: dict(Counter(row["module_id"] for row in items))
        for name, items in split["split_rows"].items()
    }
    unique_fingerprints = len({row["attack_fingerprint"] for row in rows})
    unique_samples = len({row["sample_id"] for row in rows})

    manifest = {
        "artifact": "Hermes SeqGAN V3 local corpus preparation",
        "created_at": created_at,
        "archive_path": str(archive),
        "archive_sha256": archive_sha256,
        "source_dataset_title": dataset_manifest.get("title"),
        "source_dataset_version": dataset_manifest.get("version"),
        "source_scope": dataset_manifest.get("scope"),
        "source_corpus_role": dataset_manifest.get("corpus_role"),
        "source_validation_policy": dataset_manifest.get("validation_policy"),
        "qa_report": qa_report,
        "checksum_report": checksum_report,
        "static_validation_summary": static_summary,
        "counts": {
            "rows": len(rows),
            "unique_sample_ids": unique_samples,
            "unique_attack_fingerprints": unique_fingerprints,
            "by_module": dict(by_module),
        },
        "split_policy": {
            "unit": "attack_fingerprint",
            "ratios": {
                "train": ratios.train,
                "validation": ratios.validation,
                "frozen_test": ratios.frozen_test,
            },
            "hash": "sha256(attack_fingerprint) first 32 bits modulo 100",
            "payload_exported": False,
            "reason": "splits contain metadata only; raw payload remains local in source archive",
        },
        "split_counts": split_counts,
        "split_counts_by_module": split_by_module,
        "leakage_check": split["overlaps"],
        "runtime_claims": {
            "runtime_claim_allowed": False,
            "postgres_runtime_status": "not_run",
            "truth_oracle_status": "not_run",
            "exploit_confirmed": False,
            "next_required_step": "run local PostgreSQL/WAF lab validation before promoting findings",
        },
    }
    write_json(output_dir / "seqgan_v3_corpus_manifest.json", manifest)
    write_json(output_dir / "splits" / "split_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Hermes SeqGAN V3 local corpus metadata and frozen splits.")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", default=Path("training/seqgan/data/processed/v3"), type=Path)
    parser.add_argument("--train", default=80, type=int)
    parser.add_argument("--validation", default=10, type=int)
    parser.add_argument("--frozen-test", default=10, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = prepare_archive(
        args.archive,
        args.output,
        SplitRatios(args.train, args.validation, args.frozen_test),
    )
    print(json.dumps({
        "status": "ok",
        "rows": manifest["counts"]["rows"],
        "archive_sha256": manifest["archive_sha256"],
        "split_counts": manifest["split_counts"],
        "output": str(args.output),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
