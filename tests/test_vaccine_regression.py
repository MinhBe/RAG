from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.vaccine_regression import (
    VaccineCaseError,
    run_vaccine_regression,
    vaccine_row_to_case,
)


def valid_row(case_id: str = "VACCINE-0001") -> dict:
    return {
        "case_id": case_id,
        "sample_id": "sample-1",
        "source": {
            "generator_kind": "full_pytorch_seqgan_v3_oracle_projected",
            "generator_version": "test",
            "payload_redacted": True,
            "payload_exported": False,
        },
        "evidence_contract": {
            "controlled_lab_only": True,
            "modsecurity_first_gate": True,
            "waf_access_logged": True,
            "waf_audit_logged": True,
            "lab_oracle": "postgres_boolean_truth_oracle",
            "lab_oracle_matched": True,
        },
        "threat_signal": {
            "verified_threat_signal": True,
            "signal_type": "sql_boolean_predicate_probe",
            "quality_label": "accepted_for_defensive_vaccine_dataset",
            "ambiguity": "low",
            "not_public_target": True,
        },
        "hermes_skill_evaluation": {
            "skill_family": "web-application-input-validation-and-sql-injection-triage",
            "framework_mapping": {"mitre_attack": ["T1190"]},
        },
    }


def test_vaccine_row_maps_to_redacted_lab_case() -> None:
    case = vaccine_row_to_case(valid_row())
    assert case.environment == "lab"
    assert case.evidence[0].redaction_status == "redacted"
    assert case.evidence[0].severity_hint == "high"
    assert case.evidence[0].attributes["payload_redacted"] is True


def test_vaccine_row_rejects_payload_material() -> None:
    row = valid_row()
    row["payload"] = "must-not-enter-regression"
    with pytest.raises(VaccineCaseError, match="raw payload material"):
        vaccine_row_to_case(row)


def test_vaccine_regression_runs_full_case_pipeline(tmp_path: Path) -> None:
    dataset = tmp_path / "vaccine.jsonl"
    rows = [valid_row("VACCINE-0001"), valid_row("VACCINE-0002")]
    dataset.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    summary = run_vaccine_regression(dataset, output)

    assert summary["status"] == "ok"
    assert summary["processed_cases"] == 2
    assert summary["positive_routing_recall"] == 1.0
    assert summary["hitl_pending_count"] == 2
    assert summary["remediation_violation_count"] == 0
    assert summary["external_model_calls"] == 0
    assert summary["claim_scope"]["false_positive_rate_measured"] is False
