from datetime import UTC, datetime
from uuid import UUID

from app.core.settings import settings
from app.schemas.evidence import Evidence
from supabase import Client, create_client


def supabase_is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_secret_key)


def get_supabase_client() -> Client:
    if not supabase_is_configured():
        raise RuntimeError("Supabase server credentials are not configured")
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def persist_triage_result(
    *,
    run_uuid: UUID,
    request_id: str,
    evidence: list[Evidence],
    findings: list[dict],
    approval_status: str,
) -> str:
    client = get_supabase_client()
    run_id = str(run_uuid)
    now = datetime.now(UTC).isoformat()
    client.table("runs").insert(
        {
            "id": run_id,
            "started_at": now,
            "status": "triaged",
            "metadata": {
                "request_id": request_id,
                "evidence_count": len(evidence),
                "finding_count": len(findings),
                "approval_status": approval_status,
            },
        }
    ).execute()

    evidence_rows = [
        {
            "id": item.evidence_id,
            "run_id": run_id,
            "source": item.source,
            "event_type": item.event_type,
            "content": item.model_dump(mode="json"),
        }
        for item in evidence
    ]
    if evidence_rows:
        client.table("evidence").insert(evidence_rows).execute()

    finding_rows = [
        {
            "id": finding["finding_id"],
            "run_id": run_id,
            "severity": finding["severity"],
            "disposition": finding["disposition"],
            "title": finding["title"],
            "evidence_refs": finding["evidence_refs"],
            "analysis": {
                "rationale": finding.get("rationale"),
                "detector": finding.get("detector"),
                "created_at": finding.get("created_at"),
            },
            "validation_status": finding["validation_status"],
        }
        for finding in findings
    ]
    if finding_rows:
        client.table("findings").insert(finding_rows).execute()

    client.table("runs").update(
        {
            "finished_at": datetime.now(UTC).isoformat(),
            "status": approval_status,
            "metadata": {
                "request_id": request_id,
                "evidence_count": len(evidence),
                "finding_count": len(findings),
                "approval_status": approval_status,
            },
        }
    ).eq("id", run_id).execute()
    return "stored"
