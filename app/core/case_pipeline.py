import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.analyzers.rules import route_for_review
from app.core.policy import review_policy
from app.observability.jsonl import JsonlTraceWriter
from app.providers.ai.analyst import CaseAnalystProvider
from app.schemas.case import AnalystDraft, CaseRecord
from app.schemas.evidence import Evidence

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _safe_file_stem(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _highest_severity(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "low"
    return max(findings, key=lambda item: SEVERITY_RANK[item["severity"]])["severity"]


def _extract_assets(evidence: list[Evidence]) -> list[str]:
    assets: set[str] = set()
    for item in evidence:
        for key in ("host", "asset", "hostname", "dst_ip", "src_ip"):
            value = item.attributes.get(key)
            if isinstance(value, str) and value:
                assets.add(value)
    return sorted(assets) or ["UNKNOWN_OR_REDACTED_ASSET"]


def _build_analyst_draft(
    case: CaseRecord,
    findings: list[dict[str, Any]],
) -> AnalystDraft:
    severity = _highest_severity(findings)
    evidence_refs = [item.evidence_id for item in case.evidence]
    if findings:
        summary = (
            f"Case {case.case_id} has {len(findings)} deterministic review "
            "finding(s). Treat this as an analyst draft, not a confirmed threat."
        )
        action = (
            "Review the cited evidence, verify asset context, then choose "
            "escalate, close, or need_more_evidence. Do not remediate from "
            "this draft alone."
        )
    else:
        summary = (
            f"Case {case.case_id} produced no high/critical deterministic "
            "review findings in the current rule set."
        )
        action = (
            "Analyst may close after review or request more evidence if the "
            "source context is incomplete. No automated closure is performed."
        )
    return AnalystDraft(
        summary=summary,
        severity=severity,
        evidence_refs=evidence_refs,
        affected_assets=_extract_assets(case.evidence),
        recommended_action=action,
        decision_options=["escalate", "close", "need_more_evidence"],
        safety_boundaries=[
            "no_autonomous_remediation",
            "no_security_control_change",
            "human_decision_required_for_escalation_or_closure",
        ],
    )


def _render_html_report(report: dict[str, Any]) -> str:
    findings = "".join(
        f"<li>{escape(item['title'])} — {escape(item['severity'])}</li>"
        for item in report["findings"]
    ) or "<li>No deterministic findings.</li>"
    refs = "".join(
        f"<li>{escape(ref)}</li>" for ref in report["analyst_draft"]["evidence_refs"]
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Hermes A case report</title></head>
<body>
<h1>Hermes A case report — {escape(report['case_id'])}</h1>
<p><strong>Status:</strong> {escape(report['case_status'])}</p>
<p><strong>Approval:</strong> {escape(report['approval_status'])}</p>
<p><strong>Draft source:</strong> {escape(report.get('llm_metadata', {}).get('draft_source', 'unknown'))}</p>
<p><strong>Remediation executed:</strong> {report['remediation_executed']}</p>
<h2>Analyst draft</h2>
<p>{escape(report['analyst_draft']['summary'])}</p>
<p><strong>Recommended action:</strong>
{escape(report['analyst_draft']['recommended_action'])}</p>
<h2>Evidence refs</h2><ul>{refs}</ul>
<h2>Findings</h2><ul>{findings}</ul>
<h2>Safety boundary</h2>
<p>This artifact is a post-audit draft. It does not confirm a threat and does
not authorize remediation.</p>
</body>
</html>
"""


def run_case_pipeline(
    case: CaseRecord,
    artifacts_root: Path | str = Path("artifacts/hermes_a"),
    analyst_provider: CaseAnalystProvider | None = None,
) -> dict[str, Any]:
    request_id = f"REQ-A-{uuid4().hex[:12]}"
    run_uuid = uuid4()
    root = Path(artifacts_root)
    trace_path = root / "runs" / request_id / "trace.jsonl"
    trace = JsonlTraceWriter(trace_path)
    trace.write(
        {
            "event": "case_received",
            "request_id": request_id,
            "run_uuid": str(run_uuid),
            "case_id": case.case_id,
            "evidence_count": len(case.evidence),
        }
    )
    evidence = [Evidence.model_validate(item) for item in case.evidence]
    trace.write({"event": "schema_validated", "request_id": request_id})
    findings = []
    for item in evidence:
        finding = route_for_review(item)
        if finding:
            findings.append(finding.model_dump(mode="json"))
    trace.write(
        {
            "event": "deterministic_triage_finished",
            "request_id": request_id,
            "findings": len(findings),
        }
    )
    policy = review_policy(findings)
    deterministic_draft = _build_analyst_draft(case, findings)
    provider = analyst_provider or CaseAnalystProvider()
    draft, llm_metadata = provider.draft(case, findings, deterministic_draft)
    trace.write(
        {
            "event": "analyst_draft_created",
            "request_id": request_id,
            "draft_source": llm_metadata["draft_source"],
            "llm_enabled": llm_metadata["llm_enabled"],
        }
    )
    trace.write(
        {
            "event": "policy_gate",
            "request_id": request_id,
            "approval_required": policy["approval_required"],
            "approval_status": policy["approval_status"],
        }
    )
    case_status = (
        "waiting_analyst_review"
        if policy["approval_required"]
        else "draft_ready_for_analyst_review"
    )
    report = {
        "product_lane": "hermes_a_core_post_audit",
        "request_id": request_id,
        "run_uuid": str(run_uuid),
        "case_id": case.case_id,
        "case_title": case.title,
        "case_status": case_status,
        "approval_required": policy["approval_required"],
        "approval_status": policy["approval_status"],
        "remediation_executed": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "analyst_draft": draft.model_dump(mode="json"),
        "llm_metadata": llm_metadata,
        "findings": findings,
        "trace_path": str(trace_path),
        "schema_version": "1.0",
    }
    root.mkdir(parents=True, exist_ok=True)
    stem = _safe_file_stem(case.case_id)
    json_path = root / f"{stem}_report.json"
    html_path = root / f"{stem}_report.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path.write_text(_render_html_report(report), encoding="utf-8")
    report["report_json_path"] = str(json_path)
    report["report_html_path"] = str(html_path)
    trace.write(
        {
            "event": "reports_written",
            "request_id": request_id,
            "json_path": str(json_path),
            "html_path": str(html_path),
        }
    )
    trace.write({"event": "run_finished", "request_id": request_id})
    return report
