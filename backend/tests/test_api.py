import json

import pytest
from fastapi.testclient import TestClient

from app.agents.knowledge import NOT_FOUND, extract_citations
from app.main import app


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm"] == "offline-extractive"
    assert body["chunks"] > 10


def test_chat_streams_steps_sources_tokens_and_done(client):
    res = client.post("/api/chat", json={"message": "Sofa được bảo hành mấy năm?"})
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    kinds = [e for e, _ in events]

    assert kinds[0] == "step"
    assert kinds.index("sources") < kinds.index("token") < kinds.index("done")
    sources = next(d for e, d in events if e == "sources")["sources"]
    assert sources[0]["doc_id"] == "CS-BAOHANH"

    done = events[-1][1]
    answer = "".join(d["text"] for e, d in events if e == "token")
    assert done["answer"] == answer
    assert "36 tháng" in answer
    assert done["citations"] and not done["invalid_citations"]
    assert done["latency_ms"]["total"] >= done["latency_ms"]["retrieval"]


def test_off_topic_question_is_declined(client):
    events = parse_sse(client.post("/api/chat", json={"message": "xyzzy qwfp"}).text)
    sources = next(d for e, d in events if e == "sources")["sources"]
    assert sources == []
    assert events[-1][1]["answer"] == NOT_FOUND


def test_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_document_endpoints(client):
    docs = client.get("/api/documents").json()
    assert {d["doc_id"] for d in docs} >= {"CS-DOITRA", "CS-HOANTIEN"}
    assert "Thời hạn" in client.get("/api/documents/CS-DOITRA").json()["markdown"]
    assert client.get("/api/documents/nope").status_code == 404


def test_extract_citations_flags_out_of_range():
    assert extract_citations("A [1] B [3][1] C [9]", n_sources=3) == ([1, 3], [9])
