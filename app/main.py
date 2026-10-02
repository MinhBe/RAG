from fastapi import FastAPI
from pydantic import BaseModel

from app.core.pipeline import run_triage
from app.core.settings import settings
from app.providers.ai.router import RouterProvider
from app.schemas.evidence import Evidence

app = FastAPI(title="Hermes SOC Post-Audit", version="0.2.0")


class TriageRequest(BaseModel):
    evidence: list[Evidence]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "defensive-post-audit"}


@app.get("/health/providers")
async def provider_health() -> dict:
    return {
        "ai_gateway": await RouterProvider().status(),
        "supabase_configured": bool(settings.supabase_url and settings.supabase_secret_key),
    }


@app.post("/v1/triage")
def triage(request: TriageRequest) -> dict:
    return run_triage(request.evidence)
