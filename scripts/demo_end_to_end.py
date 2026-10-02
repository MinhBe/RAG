import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def wait_for_health(client: httpx.Client) -> httpx.Response:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            response = client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                return response
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Hermes did not become healthy: {last_error}")


def main() -> None:
    with httpx.Client(timeout=10.0) as client:
        health = wait_for_health(client)
        print("health", health.status_code, health.json())

        providers = client.get(f"{BASE_URL}/health/providers")
        print("providers", providers.status_code, providers.json())
        require(providers.status_code == 200, "Provider health failed")
        require(
            providers.json().get("supabase_configured") is True,
            "Supabase is not configured",
        )

        payload = {
            "evidence": [
                {
                    "source": "synthetic-demo",
                    "event_type": "auth",
                    "severity_hint": "high",
                    "message": "Synthetic failed-login cluster requiring analyst review.",
                    "redaction_status": "synthetic",
                }
            ]
        }
        triage = client.post(f"{BASE_URL}/v1/triage", json=payload)
        body = triage.json()
        print(
            "triage",
            triage.status_code,
            body.get("approval_status"),
            body.get("storage_status"),
        )
        require(triage.status_code == 200, "Triage request failed")
        require(body.get("storage_status") == "stored", "Triage result was not stored")
        run_uuid = body["run_uuid"]

        audit = client.get(f"{BASE_URL}/v1/runs/{run_uuid}")
        audit_body = audit.json()
        print(
            "readback",
            audit.status_code,
            "evidence=",
            len(audit_body.get("evidence", [])),
            "findings=",
            len(audit_body.get("findings", [])),
        )
        require(audit.status_code == 200, "Audit readback failed")
        require(audit_body["run"]["id"] == run_uuid, "Readback run id mismatch")
        require(len(audit_body.get("evidence", [])) == 1, "Evidence row missing")
        require(len(audit_body.get("findings", [])) == 1, "Finding row missing")
        latest = client.get(f"{BASE_URL}/v1/runs/latest")
        print("latest", latest.status_code, latest.json().get("run", {}).get("id"))
        require(latest.status_code == 200, "Latest run readback failed")
        print("PASS end-to-end demo run", run_uuid)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
