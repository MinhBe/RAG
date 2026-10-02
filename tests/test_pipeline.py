from app.core import pipeline
from app.core.pipeline import run_triage
from app.schemas.evidence import Evidence


def test_high_hint_routes_to_human_review(monkeypatch):
    monkeypatch.setattr(pipeline, "supabase_is_configured", lambda: False)
    evidence = Evidence(
        source="synthetic", event_type="auth", severity_hint="high", message="fixture"
    )
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


def test_low_hint_does_not_create_security_claim(monkeypatch):
    monkeypatch.setattr(pipeline, "supabase_is_configured", lambda: False)
    evidence = Evidence(
        source="synthetic", event_type="process", severity_hint="low", message="fixture"
    )
    result = run_triage([evidence])
    assert result["findings"] == []
    assert result["approval_required"] is False
    assert result["approval_status"] == "not_required"
    assert result["storage_status"] == "disabled"


def test_storage_path_records_stored_status(monkeypatch):
    monkeypatch.setattr(pipeline, "supabase_is_configured", lambda: True)

    def fake_persist_triage_result(**kwargs):
        assert kwargs["request_id"].startswith("REQ-")
        assert len(kwargs["evidence"]) == 1
        return "stored"

    monkeypatch.setattr(pipeline, "persist_triage_result", fake_persist_triage_result)
    evidence = Evidence(
        source="synthetic", event_type="auth", severity_hint="high", message="fixture"
    )
    result = run_triage([evidence])
    assert result["storage_status"] == "stored"
