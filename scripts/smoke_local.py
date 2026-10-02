import httpx

base = "http://127.0.0.1:8000"
with httpx.Client(timeout=5.0) as client:
    health = client.get(base + "/health")
    print("health", health.status_code, health.json())
    providers = client.get(base + "/health/providers")
    print("providers", providers.status_code, providers.json())
    payload = {"evidence": [{"source": "synthetic", "event_type": "auth",
                            "severity_hint": "high", "message": "fixture"}]}
    triage = client.post(base + "/v1/triage", json=payload)
    body = triage.json()
    print("triage", triage.status_code, body["approval_status"],
          len(body["findings"]))
    private = {"evidence": [{"source": "host", "event_type": "auth",
                            "message": "fixture", "redaction_status": "private"}]}
    rejected = client.post(base + "/v1/triage", json=private)
    print("private_rejected", rejected.status_code)
