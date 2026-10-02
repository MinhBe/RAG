from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "defensive-post-audit"


def test_triage_schema(monkeypatch):
    monkeypatch.setattr("app.core.pipeline.supabase_is_configured", lambda: False)
    payload = {"evidence": [{"source": "synthetic", "event_type": "auth", "severity_hint": "high", "message": "fixture"}]}
    response = client.post("/v1/triage", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is True
    assert body["approval_status"] == "pending_human_review"


def test_unredacted_evidence_is_rejected():
    payload = {"evidence": [{"source": "host", "event_type": "auth", "message": "fixture", "redaction_status": "private"}]}
    response = client.post("/v1/triage", json=payload)
    assert response.status_code == 422


def test_latest_run_requires_supabase(monkeypatch):
    monkeypatch.setattr(main_module, "supabase_is_configured", lambda: False)
    response = client.get("/v1/runs/latest")
    assert response.status_code == 503


def test_latest_run_returns_audit_trail(monkeypatch):
    run_id = str(uuid4())
    monkeypatch.setattr(main_module, "supabase_is_configured", lambda: True)
    monkeypatch.setattr(
        main_module,
        "get_latest_run_audit_trail",
        lambda: {"run": {"id": run_id}, "evidence": [], "findings": []},
    )
    response = client.get("/v1/runs/latest")
    assert response.status_code == 200
    assert response.json()["run"]["id"] == run_id


def test_run_by_uuid_not_found(monkeypatch):
    run_id = uuid4()
    monkeypatch.setattr(main_module, "supabase_is_configured", lambda: True)
    monkeypatch.setattr(main_module, "get_run_audit_trail", lambda _: None)
    response = client.get(f"/v1/runs/{run_id}")
    assert response.status_code == 404
