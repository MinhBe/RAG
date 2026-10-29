"""Phê duyệt có người thật: gửi -> chờ -> chuyên gia duyệt/từ chối -> chat đọc lại kết quả."""

import pytest
from fastapi.testclient import TestClient

from app.api import routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi import FastAPI

    monkeypatch.setattr(routes, "_ESC_FILE", tmp_path / "escalations.json")
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_full_loop_approved_with_expert_reply(client):
    esc = client.post("/api/escalate", json={"question": "Bộ luật Lao động 2026 nói gì về sa thải?"}).json()
    assert client.get(f"/api/escalations/{esc['id']}").json()["status"] == "pending"

    r = client.patch(f"/api/escalations/{esc['id']}",
                     json={"status": "approved", "reply": "Chưa có BLLĐ 2026; hiện áp dụng Điều 125 BLLĐ 2019."})
    assert r.status_code == 200
    got = client.get(f"/api/escalations/{esc['id']}").json()
    assert got["status"] == "approved" and "Điều 125" in got["reply"] and got["resolved_at"]


def test_approve_requires_an_answer(client):
    esc = client.post("/api/escalate", json={"question": "q"}).json()
    r = client.patch(f"/api/escalations/{esc['id']}", json={"status": "approved", "reply": "  "})
    assert r.status_code == 422
    assert client.get(f"/api/escalations/{esc['id']}").json()["status"] == "pending"


def test_deny_with_reason_and_reject_unknown_status(client):
    esc = client.post("/api/escalate", json={"question": "q"}).json()
    assert client.patch(f"/api/escalations/{esc['id']}", json={"status": "maybe"}).status_code == 422
    r = client.patch(f"/api/escalations/{esc['id']}", json={"status": "denied", "reply": "Ngoài phạm vi"})
    assert r.json()["status"] == "denied" and r.json()["reply"] == "Ngoài phạm vi"


def test_unknown_id_is_404(client):
    assert client.get("/api/escalations/nope").status_code == 404
