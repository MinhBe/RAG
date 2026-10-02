from app.core.pipeline import run_triage
from app.schemas.evidence import Evidence


def test_high_hint_routes_to_human_review():
    evidence = Evidence(source="synthetic", event_type="auth", severity_hint="high", message="fixture")
    result = run_triage([evidence])
    assert result["approval_required"] is True
    assert result["approval_status"] == "pending_human_review"
    assert result["storage_status"] == "disabled"
    assert result["request_id"].startswith("REQ-")
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["disposition"] == "escalate"
    assert finding["evidence_refs"] == [evidence.evidence_id]
    assert "does not assert" in finding["rationale"]


def test_low_hint_does_not_create_security_claim():
    evidence = Evidence(source="synthetic", event_type="process", severity_hint="low", message="fixture")
    result = run_triage([evidence])
    assert result["findings"] == []
    assert result["approval_required"] is False
    assert result["approval_status"] == "not_required"
    assert result["storage_status"] == "disabled"
