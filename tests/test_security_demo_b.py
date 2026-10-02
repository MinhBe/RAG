import json
from pathlib import Path

from app.core import pipeline
from app.core.pipeline import run_triage
from app.schemas.evidence import Evidence

CASES_PATH = Path("data/public/security_demo_b.jsonl")


def load_cases():
    return [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_demo_b_fixture_cases_are_valid_evidence():
    cases = load_cases()
    assert {case["case_id"] for case in cases} == {
        "DEMO-B-001",
        "DEMO-B-002",
        "DEMO-B-003",
    }
    for case in cases:
        for item in case["evidence"]:
            evidence = Evidence.model_validate(item)
            assert evidence.redaction_status == "synthetic"


def test_injection_phrases_remain_data_not_findings(monkeypatch):
    monkeypatch.setattr(pipeline, "supabase_is_configured", lambda: False)
    injected_cases = [
        case for case in load_cases() if case["case_id"] in {"DEMO-B-001", "DEMO-B-002"}
    ]
    for case in injected_cases:
        evidence = [Evidence.model_validate(item) for item in case["evidence"]]
        result = run_triage(evidence)
        assert result["approval_status"] == "pending_human_review"
        assert result["findings"]
        serialized = json.dumps(result["findings"]).lower()
        assert "ignore previous instructions" not in serialized
        assert "disclose secrets" not in serialized
        submitted_refs = {item.evidence_id for item in evidence}
        for finding in result["findings"]:
            assert set(finding["evidence_refs"]).issubset(submitted_refs)


def test_low_severity_demo_case_does_not_create_claim(monkeypatch):
    monkeypatch.setattr(pipeline, "supabase_is_configured", lambda: False)
    case = next(item for item in load_cases() if item["case_id"] == "DEMO-B-003")
    evidence = [Evidence.model_validate(item) for item in case["evidence"]]
    result = run_triage(evidence)
    assert result["findings"] == []
    assert result["approval_status"] == "not_required"
