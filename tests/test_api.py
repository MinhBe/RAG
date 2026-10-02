from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "defensive-post-audit"


def test_triage_schema():
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
