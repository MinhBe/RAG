from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
RUNTIME = ROOT / "training/seqgan/data/processed/v3/runtime"
BOOL = ROOT / "artifacts/boolean_vaccine"
GEN = ROOT / "training/seqgan/data/processed/v3/generated/latest"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def count_jsonl(path: Path, key: str | None = None, value: Any = None) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if key is None or row.get(key) == value:
            total += 1
    return total


def gate(name: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def main() -> None:
    waf = load_json(RUNTIME / "generated_waf_probe.summary.json")
    pg = load_json(RUNTIME / "generated_postgres_probe.summary.json")
    manifest = load_json(GEN / "generator_manifest.json")
    seeds = load_json(BOOL / "boolean_seed_discovery.summary.json")
    generated = load_json(BOOL / "generated_acceptance.redacted.summary.json")

    gates = [
        gate(
            "existing_modsecurity_probe",
            waf.get("status") == "ok"
            and waf.get("samples", 0) >= 50
            and waf.get("waf_access_logged") == waf.get("samples")
            and waf.get("waf_audit_logged") == waf.get("samples"),
            waf,
        ),
        gate(
            "existing_postgres_oracle_probe",
            pg.get("status") == "ok"
            and pg.get("samples", 0) >= 50
            and pg.get("matched") == pg.get("samples"),
            pg,
        ),
        gate(
            "seqgan_candidate_lineage",
            manifest.get("status") == "ok"
            and manifest.get("projected", 0) >= 50
            and manifest.get("payload_exported_in_manifest") is False,
            {
                "status": manifest.get("status"),
                "projected": manifest.get("projected"),
                "raw_full_seqgan_rows": manifest.get("raw_full_seqgan_rows"),
                "raw_full_seqgan_accepted_rows": manifest.get("raw_full_seqgan_accepted_rows"),
                "payload_exported_in_manifest": manifest.get("payload_exported_in_manifest"),
                "honesty_boundary": manifest.get("honesty_boundary"),
            },
        ),
        gate(
            "five_boolean_seeds_through_waf_backend_oracle",
            seeds.get("status") == "ok" and seeds.get("accepted", 0) >= 5,
            seeds,
        ),
        gate(
            "fifty_generated_samples_through_waf_backend_oracle",
            generated.get("status") == "ok"
            and generated.get("accepted", 0) >= 50
            and generated.get("backend_reached", 0) >= 50
            and generated.get("waf_access_logged", 0) >= 50,
            generated,
        ),
        gate(
            "public_artifacts_redacted",
            count_jsonl(BOOL / "generated_acceptance.redacted.jsonl", "payload_redacted", True) >= 50
            if (BOOL / "generated_acceptance.redacted.jsonl").exists()
            else False,
            {
                "redacted_generated_rows": count_jsonl(
                    BOOL / "generated_acceptance.redacted.jsonl", "payload_redacted", True
                ),
                "public_generated_path": str(BOOL / "generated_acceptance.redacted.jsonl"),
                "private_generated_path": str(BOOL / "private/generated_acceptance.local.jsonl"),
            },
        ),
    ]
    missing = [g["name"] for g in gates if not g["passed"]]
    hard_blockers = []
    if "five_boolean_seeds_through_waf_backend_oracle" in missing:
        hard_blockers.append("backend_oracle_behind_modsecurity_not_verified")
    if "fifty_generated_samples_through_waf_backend_oracle" in missing:
        hard_blockers.append("generated_candidates_not_replayed_through_same_waf_backend_oracle_path")

    summary = {
        "status": "PASS" if not missing else "FAIL",
        "definition_of_done_passed": not missing,
        "passed_gates": [g["name"] for g in gates if g["passed"]],
        "failed_gates": missing,
        "hard_blockers": hard_blockers,
        "gates": gates,
    }
    out = BOOL / "definition_of_done.summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
