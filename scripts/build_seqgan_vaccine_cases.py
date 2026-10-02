from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_POSTGRES = Path("training/seqgan/data/processed/v3/runtime/generated_postgres_probe.jsonl")
DEFAULT_WAF = Path("training/seqgan/data/processed/v3/runtime/generated_waf_probe.jsonl")
DEFAULT_MANIFEST = Path("training/seqgan/data/processed/v3/generated/latest/generator_manifest.json")
DEFAULT_METADATA = Path("training/seqgan/data/processed/v3/generated/latest/generated_candidates.metadata.jsonl")
DEFAULT_OUTPUT = Path("artifacts/demo_b/seqgan_vaccine_cases.jsonl")
DEFAULT_SUMMARY = Path("artifacts/demo_b/seqgan_vaccine_cases.summary.json")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def by_sample(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("sample_id")): row for row in rows if row.get("sample_id")}


def classify(row: dict[str, Any]) -> dict[str, Any]:
    module_id = str(row.get("module_id", "unknown"))
    grammar = str(row.get("root_grammar_id", "unknown"))
    y_level = str(row.get("y_level", "unknown"))
    expected_truth = bool(row.get("expected_truth"))
    lower = f"{module_id} {grammar} {y_level}".lower()
    if "boolean" in lower or "y1" in lower:
        category = "sql_boolean_predicate_probe"
        skill_family = "web-application-input-validation-and-sql-injection-triage"
    elif "error" in lower:
        category = "sql_error_surface_probe"
        skill_family = "web-application-error-surface-triage"
    else:
        category = "web-application-payload-triage"
        skill_family = "generic-web-threat-triage"
    return {
        "category": category,
        "skill_family": skill_family,
        "framework_mapping": {
            "mitre_attack": ["T1190"],
            "nist_csf": ["DE.CM", "DE.AE", "PR.DS"],
            "d3fend": ["D3-IVA", "D3-AL", "D3-ANAA"],
        },
        "rationale": {
            "module_id": module_id,
            "root_grammar_id": grammar,
            "y_level": y_level,
            "expected_truth": expected_truth,
        },
    }


def build_cases(
    postgres_rows: list[dict[str, Any]],
    waf_rows: list[dict[str, Any]],
    metadata_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    pg = by_sample(postgres_rows)
    waf = by_sample(waf_rows)
    meta = by_sample(metadata_rows)
    cases: list[dict[str, Any]] = []
    for sample_id in sorted(set(pg) & set(waf)):
        pg_row = pg[sample_id]
        waf_row = waf[sample_id]
        meta_row = meta.get(sample_id, {})
        pg_matched = bool(pg_row.get("matched"))
        waf_access = bool(waf_row.get("waf_access_logged"))
        waf_audit = bool(waf_row.get("waf_audit_logged"))
        http_ok = 0 < int(waf_row.get("http_status", 0)) < 500
        verified = pg_matched and waf_access and waf_audit and http_ok
        if not verified:
            continue
        merged = {**meta_row, **pg_row, **waf_row}
        classification = classify(merged)
        case = {
            "case_id": f"VACCINE-{len(cases) + 1:04d}",
            "sample_id": sample_id,
            "created_at": datetime.now(UTC).isoformat(),
            "source": {
                "generator_kind": manifest.get("generator_kind") or merged.get("generator_kind"),
                "generator_version": manifest.get("generator_version"),
                "generator_run_id": merged.get("generator_run_id") or manifest.get("generator_run_id"),
                "payload_exported": False,
                "payload_redacted": True,
                "lineage_retained_in_local_artifacts": True,
            },
            "evidence_contract": {
                "modsecurity_first_gate": True,
                "waf_access_logged": waf_access,
                "waf_audit_logged": waf_audit,
                "waf_mode": waf_row.get("waf_mode"),
                "http_status_class": f"{int(waf_row.get('http_status', 0)) // 100}xx",
                "lab_oracle": "postgres_boolean_truth_oracle",
                "lab_oracle_matched": pg_matched,
                "controlled_lab_only": True,
            },
            "threat_signal": {
                "verified_threat_signal": True,
                "signal_type": classification["category"],
                "quality_label": "accepted_for_defensive_vaccine_dataset",
                "ambiguity": "low",
                "not_public_target": True,
            },
            "hermes_skill_evaluation": classification,
        }
        cases.append(case)
        if len(cases) >= limit:
            break
    return cases


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build redacted SeqGAN vaccine cases from controlled lab evidence.")
    parser.add_argument("--postgres", type=Path, default=DEFAULT_POSTGRES)
    parser.add_argument("--waf", type=Path, default=DEFAULT_WAF)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    cases = build_cases(
        load_jsonl(args.postgres),
        load_jsonl(args.waf),
        load_jsonl(args.metadata),
        load_json(args.manifest),
        args.limit,
    )
    write_jsonl(args.output, cases)
    by_category = Counter(case["threat_signal"]["signal_type"] for case in cases)
    summary = {
        "status": "ok" if len(cases) >= args.limit else "partial",
        "requested": args.limit,
        "cases": len(cases),
        "payloads_redacted": True,
        "controlled_lab_only": True,
        "modsecurity_first_gate": True,
        "lab_oracle": "postgres_boolean_truth_oracle",
        "ambiguity": "low" if cases else "none",
        "categories": dict(sorted(by_category.items())),
        "output": str(args.output),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
