import json
from pathlib import Path
from typing import Any

from app.core.case_pipeline import run_case_pipeline
from app.schemas.case import CaseRecord

SAMPLE_CASE_PATH = Path("data/public/hermes_a_sample_case.json")


def _load_latest_case_report(case_id: str) -> dict[str, Any] | None:
    report_path = Path("artifacts/hermes_a") / f"{case_id}_report.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def format_case_report(report: dict[str, Any]) -> str:
    draft = report["analyst_draft"]
    lines = [
        f"Hermes A case {report['case_id']}",
        f"Status: {report['case_status']}",
        f"Approval: {report['approval_status']}",
        f"Severity: {draft['severity']}",
        f"Draft source: {report.get('llm_metadata', {}).get('draft_source', 'unknown')}",
        "",
        draft["summary"],
        "",
        "Recommended action:",
        draft["recommended_action"],
        "",
        f"Trace: {report['trace_path']}",
    ]
    return "\n".join(lines)


def handle_telegram_message(text: str) -> str:
    normalized = text.strip()
    lowered = normalized.lower()
    if lowered in {"/start", "start", "help", "/help"}:
        return (
            "Hermes A Telegram adapter ready. Commands:\n"
            "/demo_a - run the sample post-audit case\n"
            "/case CASE-A-001 - show latest local case report\n"
            "/health - adapter health"
        )
    if lowered == "/health":
        return "Hermes A Telegram adapter: ok"
    if lowered in {"/demo_a", "demo_a", "demo a"}:
        payload = json.loads(SAMPLE_CASE_PATH.read_text(encoding="utf-8-sig"))
        case = CaseRecord.model_validate(payload["case"])
        report = run_case_pipeline(case)
        return format_case_report(report)
    if lowered.startswith(("/case", "case ")):
        parts = normalized.split()
        if len(parts) != 2:
            return "Usage: /case CASE-A-001"
        case_id = parts[1]
        report = _load_latest_case_report(case_id)
        if report is None:
            return f"No local report found for {case_id}. Run /demo_a first."
        return format_case_report(report)
    return (
        "Unknown command. Use /demo_a, /case CASE-A-001, /health, or /help. "
        "Natural-language chat will be wired after persistence/readback is stable."
    )
