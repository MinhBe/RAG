from __future__ import annotations

import json
import math
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.case_pipeline import run_case_pipeline
from app.schemas.case import AnalystDraft, CaseRecord
from app.schemas.evidence import Evidence

FORBIDDEN_PAYLOAD_FIELDS = {
    "payload",
    "raw_payload",
    "request_body",
    "raw_request",
    "sql_text",
}


class VaccineCaseError(ValueError):
    pass


class DeterministicBenchmarkProvider:
    def draft(
        self,
        case: CaseRecord,
        findings: list[dict[str, Any]],
        deterministic_draft: AnalystDraft,
    ) -> tuple[AnalystDraft, dict[str, Any]]:
        del case, findings
        return deterministic_draft, {
            "llm_enabled": False,
            "draft_source": "deterministic_benchmark",
            "reason": "external_model_calls_disabled_for_regression_measurement",
        }


def _contains_forbidden_payload_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_PAYLOAD_FIELDS:
                return True
            if _contains_forbidden_payload_field(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_payload_field(item) for item in value)
    return False


def _require_true(container: dict[str, Any], key: str, scope: str) -> None:
    if container.get(key) is not True:
        raise VaccineCaseError(f"{scope}.{key} must be true")


def vaccine_row_to_case(row: dict[str, Any]) -> CaseRecord:
    if _contains_forbidden_payload_field(row):
        raise VaccineCaseError("raw payload material is not allowed in vaccine rows")

    source = row.get("source")
    contract = row.get("evidence_contract")
    signal = row.get("threat_signal")
    skill = row.get("hermes_skill_evaluation")
    if not all(isinstance(item, dict) for item in (source, contract, signal, skill)):
        raise VaccineCaseError("missing structured vaccine metadata")

    _require_true(source, "payload_redacted", "source")
    if source.get("payload_exported") is not False:
        raise VaccineCaseError("source.payload_exported must be false")
    _require_true(contract, "controlled_lab_only", "evidence_contract")
    _require_true(contract, "modsecurity_first_gate", "evidence_contract")
    _require_true(contract, "waf_access_logged", "evidence_contract")
    _require_true(contract, "waf_audit_logged", "evidence_contract")
    _require_true(contract, "lab_oracle_matched", "evidence_contract")
    _require_true(signal, "verified_threat_signal", "threat_signal")
    _require_true(signal, "not_public_target", "threat_signal")

    vaccine_case_id = str(row.get("case_id", "")).strip()
    sample_id = str(row.get("sample_id", "")).strip()
    signal_type = str(signal.get("signal_type", "")).strip()
    if not vaccine_case_id or not sample_id or not signal_type:
        raise VaccineCaseError("case_id, sample_id, and signal_type are required")

    safe_case_id = vaccine_case_id.replace("VACCINE-", "")
    case_id = f"CASE-VACCINE-{safe_case_id}"
    evidence = Evidence(
        source="seqgan_vaccine_dataset",
        event_type=signal_type,
        severity_hint="high",
        message=(
            "Redacted controlled-lab vaccine signal verified by WAF telemetry "
            "and PostgreSQL truth oracle. Payload content is intentionally absent."
        ),
        attributes={
            "vaccine_case_id": vaccine_case_id,
            "sample_id": sample_id,
            "signal_type": signal_type,
            "quality_label": signal.get("quality_label"),
            "ambiguity": signal.get("ambiguity"),
            "skill_family": skill.get("skill_family"),
            "framework_mapping": skill.get("framework_mapping", {}),
            "lab_oracle": contract.get("lab_oracle"),
            "controlled_lab_only": True,
            "modsecurity_first_gate": True,
            "payload_redacted": True,
            "generator_kind": source.get("generator_kind"),
            "generator_version": source.get("generator_version"),
        },
        redaction_status="redacted",
    )
    return CaseRecord(
        case_id=case_id,
        title=f"Vaccine regression: {signal_type}",
        description=(
            "Positive controlled-lab regression case. Used to verify Hermes "
            "Tier-1 routing and HITL invariants; not a production incident."
        ),
        submitted_by="hermes_vaccine_regression",
        environment="lab",
        evidence=[evidence],
    )


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return round(ordered[index], 3)


def run_vaccine_regression(
    dataset_path: Path,
    output_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None:
        rows = rows[:limit]

    provider = DeterministicBenchmarkProvider()
    results: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    latencies: list[float] = []
    categories: Counter[str] = Counter()
    routed = 0
    hitl_pending = 0
    remediation_violations = 0
    pipeline_errors = 0

    with tempfile.TemporaryDirectory(prefix="hermes-vaccine-regression-") as tmp:
        tmp_root = Path(tmp)
        for row in rows:
            try:
                case = vaccine_row_to_case(row)
            except (VaccineCaseError, ValueError, TypeError) as exc:
                invalid.append(
                    {
                        "case_id": str(row.get("case_id", "unknown")),
                        "reason": str(exc),
                    }
                )
                continue

            signal_type = case.evidence[0].event_type
            categories[signal_type] += 1
            started = perf_counter()
            try:
                report = run_case_pipeline(
                    case,
                    artifacts_root=tmp_root / case.case_id,
                    analyst_provider=provider,
                )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                pipeline_errors += 1
                results.append(
                    {
                        "case_id": case.case_id,
                        "signal_type": signal_type,
                        "status": "pipeline_error",
                        "error_type": type(exc).__name__,
                    }
                )
                continue

            latency_ms = (perf_counter() - started) * 1000
            latencies.append(latency_ms)
            was_routed = bool(report["findings"]) and report["approval_required"] is True
            is_pending = report["approval_status"] == "pending_human_review"
            remediation_ok = report["remediation_executed"] is False
            routed += int(was_routed)
            hitl_pending += int(is_pending)
            remediation_violations += int(not remediation_ok)
            results.append(
                {
                    "case_id": case.case_id,
                    "signal_type": signal_type,
                    "status": "ok",
                    "routed_for_review": was_routed,
                    "approval_status": report["approval_status"],
                    "findings": len(report["findings"]),
                    "remediation_executed": report["remediation_executed"],
                    "draft_source": report["llm_metadata"]["draft_source"],
                    "latency_ms": round(latency_ms, 3),
                }
            )

    eligible = len(rows) - len(invalid)
    processed = sum(1 for item in results if item["status"] == "ok")
    recall = round(routed / eligible, 4) if eligible else None
    status = "ok"
    if (
        invalid
        or pipeline_errors
        or remediation_violations
        or processed != eligible
        or routed != eligible
        or hitl_pending != eligible
    ):
        status = "partial"

    cases_path = output_path.with_name(output_path.stem + ".cases.jsonl")
    summary = {
        "status": status,
        "dataset": str(dataset_path),
        "loaded_cases": len(rows),
        "eligible_positive_cases": eligible,
        "invalid_cases": len(invalid),
        "processed_cases": processed,
        "routed_for_review": routed,
        "positive_routing_recall": recall,
        "hitl_pending_count": hitl_pending,
        "remediation_violation_count": remediation_violations,
        "pipeline_error_count": pipeline_errors,
        "external_model_calls": 0,
        "categories": dict(sorted(categories.items())),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": round(max(latencies), 3) if latencies else None,
        },
        "invalid_details": invalid,
        "case_results": str(cases_path),
        "claim_scope": {
            "positive_only_dataset": True,
            "false_positive_rate_measured": False,
            "specificity_measured": False,
            "model_fine_tuning_performed": False,
            "raw_seqgan_quality_improvement_measured": False,
            "purpose": "deterministic Tier-1 routing/HITL regression",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cases_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in results),
        encoding="utf-8",
    )
    return summary

