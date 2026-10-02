from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.pipeline import run_triage
from app.schemas.evidence import Evidence

DEFAULT_POSTGRES = Path("training/seqgan/data/processed/v3/runtime/postgres_probe_sample.jsonl")
DEFAULT_WAF = Path("training/seqgan/data/processed/v3/runtime/waf_probe_sample.jsonl")
DEFAULT_ATOMIC = Path("training/seqgan/data/processed/v3/runtime/atomic_smoke.jsonl")
DEFAULT_OUTPUT = Path("artifacts/demo_b/seqgan_lab_triage_result.json")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"no rows loaded from {path}")
    return rows


def index_by_sample(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["sample_id"]): row for row in rows}


def build_evidence(postgres_rows: list[dict[str, Any]], waf_rows: list[dict[str, Any]], atomic_rows: list[dict[str, Any]] | None = None) -> list[Evidence]:
    pg_by_sample = index_by_sample(postgres_rows)
    waf_by_sample = index_by_sample(waf_rows)
    common = sorted(set(pg_by_sample) & set(waf_by_sample))
    if not common:
        raise ValueError("no common sample_ids between PostgreSQL and WAF probe outputs")

    pg_matched = sum(1 for sample_id in common if pg_by_sample[sample_id].get("truth_oracle_status") == "matched")
    waf_access = sum(1 for sample_id in common if waf_by_sample[sample_id].get("waf_access_logged"))
    waf_audit = sum(1 for sample_id in common if waf_by_sample[sample_id].get("waf_audit_logged"))
    modules = sorted({str(pg_by_sample[sample_id].get("module_id")) for sample_id in common})
    generator_run_ids = sorted({str(pg_by_sample[sample_id].get("generator_run_id")) for sample_id in common if pg_by_sample[sample_id].get("generator_run_id")})
    generator_kinds = sorted({str(pg_by_sample[sample_id].get("generator_kind")) for sample_id in common if pg_by_sample[sample_id].get("generator_kind")})

    aggregate = Evidence(
        source="hermes_lab_seqgan_v3",
        event_type="seqgan_v3_lab_regression_summary",
        severity_hint="high",
        message=(
            "Synthetic SeqGAN V3 generated/validation slice produced PostgreSQL truth-oracle matches "
            "and WAF/CRS audit telemetry in the isolated Hermes lab. This is lab evidence only; "
            "it does not assert production exploitation."
        ),
        attributes={
            "sample_count": len(common),
            "postgres_truth_oracle_matched": pg_matched,
            "waf_access_logged": waf_access,
            "waf_audit_logged": waf_audit,
            "modules": modules,
            "lab_profile": "ubuntu2004_vm_postgres16_apache_modsecurity_crs",
            "runtime_claim_scope": "isolated_lab_only",
            "atomic_smoke_completed": sum(1 for row in (atomic_rows or []) if row.get("execution_status") == "completed"),
            "generator_run_ids": generator_run_ids,
            "generator_kinds": generator_kinds,
            "generated_candidate_count": len(common) if generator_run_ids else 0,
        },
    )
    postgres = Evidence(
        source="hermes_lab_postgres",
        event_type="postgres_truth_oracle_probe",
        severity_hint="medium",
        message="PostgreSQL sandbox evaluated the selected synthetic validation samples and returned truth-oracle metadata.",
        attributes={
            "sample_count": len(postgres_rows),
            "matched": sum(1 for row in postgres_rows if row.get("truth_oracle_status") == "matched"),
            "failed": sum(1 for row in postgres_rows if row.get("postgres_runtime_status") == "failed"),
            "payload_exported": False,
        },
    )
    waf = Evidence(
        source="hermes_lab_waf_crs",
        event_type="modsecurity_crs_probe",
        severity_hint="medium",
        message="Apache ModSecurity with OWASP CRS recorded access and audit telemetry for the selected synthetic validation samples.",
        attributes={
            "sample_count": len(waf_rows),
            "http_ok": sum(1 for row in waf_rows if int(row.get("http_status", 0)) > 0 and int(row.get("http_status", 0)) < 500),
            "waf_access_logged": sum(1 for row in waf_rows if row.get("waf_access_logged")),
            "waf_audit_logged": sum(1 for row in waf_rows if row.get("waf_audit_logged")),
            "waf_mode": "apache_modsecurity_crs_detection_only_audit_on",
            "payload_exported": False,
        },
    )
    evidence = [aggregate, postgres, waf]
    if atomic_rows:
        evidence.append(
            Evidence(
                source="hermes_lab_atomic",
                event_type="atomic_red_team_smoke",
                severity_hint="medium",
                message="A minimal Atomic Red Team smoke slice executed in the local Ubuntu lab and stored metadata only.",
                attributes={
                    "tests": len(atomic_rows),
                    "completed": sum(1 for row in atomic_rows if row.get("execution_status") == "completed"),
                    "techniques": sorted({str(row.get("technique_id")) for row in atomic_rows}),
                    "raw_output_stored": False,
                    "lab_scope": "local_vm_only",
                },
            )
        )
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize SeqGAN lab probe outputs into Hermes Evidence and run triage.")
    parser.add_argument("--postgres", default=DEFAULT_POSTGRES, type=Path)
    parser.add_argument("--waf", default=DEFAULT_WAF, type=Path)
    parser.add_argument("--atomic", default=DEFAULT_ATOMIC, type=Path)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    atomic_rows = load_jsonl(args.atomic) if args.atomic.exists() else None
    evidence = build_evidence(load_jsonl(args.postgres), load_jsonl(args.waf), atomic_rows)
    result = run_triage(evidence)
    output = {
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "triage_result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "findings": len(result.get("findings", [])), "approval_status": result.get("approval_status")}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
