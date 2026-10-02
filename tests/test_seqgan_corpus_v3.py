from __future__ import annotations

import csv
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.security_dataset import SeqGANSample

SCRIPT_PATH = Path("scripts/prepare_seqgan_corpus_v3.py")


def load_prepare_module():
    spec = importlib.util.spec_from_file_location("prepare_seqgan_corpus_v3", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv_text(rows: list[dict[str, str]]) -> str:
    from io import StringIO

    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def make_row(sample_id: str, fingerprint: str, module_id: str = "Y1_basic_boolean") -> dict[str, str]:
    return {
        "sample_id": sample_id,
        "attack_fingerprint": fingerprint,
        "module_id": module_id,
        "y_level": "Y1",
        "root_grammar_id": "PG_BOOL_R001",
        "structure_cell_id": "PG_BOOL_R001_C01",
        "boolean_pair_id": "BP_Y1_R001_C01_01",
        "expected_truth": "TRUE",
        "difficulty_level": "1",
        "contract_valid": "True",
        "required_tokens_valid": "True",
        "postgres_parse_status": "not_run",
        "postgres_runtime_status": "not_run",
        "truth_oracle_status": "not_run",
        "exploit_confirmed": "False",
        "runtime_claim_allowed": "False",
    }


def make_test_archive(path: Path) -> None:
    rows = [
        make_row("S1", "a" * 64),
        make_row("S2", "b" * 64),
        make_row("S3", "c" * 64, "Y2_boolean_variation"),
    ]
    manifest = {
        "title": "PostgreSQL Boolean Attack Structure Corpus V3",
        "version": "test",
        "scope": "PostgreSQL-only, Boolean-only, payload-only, no-context",
        "corpus_role": "attack-side structure corpus; not exploit-confirmed",
        "counts": {"total_samples": len(rows)},
        "validation_policy": {
            "postgres_parse_status": "not_run",
            "postgres_runtime_status": "not_run",
            "truth_oracle_status": "not_run",
            "runtime_claim_allowed": False,
        },
    }
    qa = {"checks": {"contract_valid_all": True}, "notes": "test"}
    attack_csv = write_csv_text(rows)
    static_csv = write_csv_text(rows)
    checksums = []
    files = {
        "Dataset/dataset_manifest.json": json.dumps(manifest),
        "Dataset/QA_REPORT.json": json.dumps(qa),
        "Dataset/B_attack_samples/attack_samples_all.csv": attack_csv,
        "Dataset/E_validation/static_validation_results.csv": static_csv,
    }
    import hashlib

    for name, content in files.items():
        checksums.append(f"{hashlib.sha256(content.encode()).hexdigest()}  {name}\n")
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        zf.writestr("SHA256.txt", "".join(checksums))


def test_prepare_archive_writes_metadata_only_splits(tmp_path):
    module = load_prepare_module()
    archive = tmp_path / "dataset.zip"
    output = tmp_path / "prepared"
    make_test_archive(archive)

    manifest = module.prepare_archive(archive, output, module.SplitRatios())

    assert manifest["counts"]["rows"] == 3
    assert manifest["checksum_report"]["bad"] == []
    assert manifest["checksum_report"]["missing"] == []
    assert manifest["split_policy"]["payload_exported"] is False
    assert output.joinpath("seqgan_v3_corpus_manifest.json").exists()
    for split_name in ["train", "validation", "frozen_test"]:
        assert output.joinpath("splits", f"{split_name}.jsonl").exists()
    for values in manifest["leakage_check"].values():
        assert values == []


def test_seqgan_sample_rejects_runtime_claim_without_oracle():
    base = {
        "sample_id": "S1",
        "generator_version": "seqgan-v3",
        "model_version": "checkpoint-test",
        "source_dataset_version": "V3_structure_conditioned_oracle_aware",
        "source_archive_sha256": "0" * 64,
        "attack_fingerprint": "a" * 64,
        "y_level": "Y1",
        "module_id": "Y1_basic_boolean",
        "root_grammar_id": "PG_BOOL_R001",
        "structure_cell_id": "PG_BOOL_R001_C01",
        "boolean_pair_id": "BP_Y1_R001_C01_01",
        "expected_truth": "TRUE",
        "split": "train",
        "contract_valid": True,
    }
    assert SeqGANSample.model_validate(base).runtime_claim_allowed is False
    with pytest.raises(ValidationError):
        SeqGANSample.model_validate({**base, "runtime_claim_allowed": True})
    promoted = SeqGANSample.model_validate(
        {
            **base,
            "runtime_claim_allowed": True,
            "postgres_runtime_status": "passed",
            "truth_oracle_status": "matched",
        }
    )
    assert promoted.runtime_claim_allowed is True
