from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core.pipeline import run_triage
from app.core.settings import settings
from app.providers.ai.router import RouterProvider
from app.providers.storage.supabase import (
    get_latest_run_audit_trail,
    get_run_audit_trail,
    supabase_is_configured,
)
from app.schemas.evidence import Evidence

app = FastAPI(title="Hermes SOC Post-Audit", version="0.3.0")


class TriageRequest(BaseModel):
    evidence: list[Evidence]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "defensive-post-audit"}


@app.get("/health/providers")
async def provider_health() -> dict:
    return {
        "ai_gateway": await RouterProvider().status(),
        "supabase_configured": bool(
            settings.supabase_url and settings.supabase_secret_key
        ),
    }


@app.post("/v1/triage")
def triage(request: TriageRequest) -> dict:
    return run_triage(request.evidence)


@app.get("/v1/runs/latest")
def latest_run() -> dict:
    if not supabase_is_configured():
        raise HTTPException(
            status_code=503, detail="Supabase storage is not configured"
        )
    audit = get_latest_run_audit_trail()
    if audit is None:
        raise HTTPException(status_code=404, detail="No persisted runs found")
    return audit


@app.get("/v1/runs/{run_uuid}")
def run_by_uuid(run_uuid: UUID) -> dict:
    if not supabase_is_configured():
        raise HTTPException(
            status_code=503, detail="Supabase storage is not configured"
        )
    audit = get_run_audit_trail(run_uuid)
    if audit is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return audit
