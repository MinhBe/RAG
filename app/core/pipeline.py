from pathlib import Path
from uuid import uuid4

from app.agent.graph import build_graph
from app.observability.jsonl import JsonlTraceWriter
from app.providers.storage.supabase import persist_triage_result, supabase_is_configured
from app.schemas.evidence import Evidence

_graph = build_graph()


def run_triage(evidence: list[Evidence]) -> dict:
    request_id = f"REQ-{uuid4().hex[:12]}"
    run_uuid = uuid4()
    trace = JsonlTraceWriter(Path("artifacts/runs") / request_id / "trace.jsonl")
    trace.write({"event": "run_started", "request_id": request_id, "run_uuid": str(run_uuid), "count": len(evidence)})
    try:
        result = _graph.invoke({"request_id": request_id, "evidence": [e.model_dump(mode="json") for e in evidence]})
        result["request_id"] = request_id
        result["run_uuid"] = str(run_uuid)
        refs = {e.evidence_id for e in evidence}
        for finding in result.get("findings", []):
            if not set(finding["evidence_refs"]).issubset(refs):
                raise ValueError("Finding contains unresolved evidence reference")

        if supabase_is_configured():
            result["storage_status"] = persist_triage_result(
                run_uuid=run_uuid,
                request_id=request_id,
                evidence=evidence,
                findings=result.get("findings", []),
                approval_status=result.get("approval_status", "unknown"),
            )
        else:
            result["storage_status"] = "disabled"

        trace.write({"event": "storage", "request_id": request_id, "status": result["storage_status"]})
        trace.write({"event": "policy_decision", "request_id": request_id, "approval_status": result.get("approval_status")})
        trace.write({"event": "run_finished", "request_id": request_id, "findings": len(result.get("findings", []))})
        return result
    except Exception as exc:
        trace.write({"event": "run_failed", "request_id": request_id, "error_type": type(exc).__name__})
        raise
