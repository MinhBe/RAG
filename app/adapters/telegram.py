import json
import re
from pathlib import Path
from typing import Any

from app.core.case_pipeline import run_case_pipeline
from app.core.chat_pipeline import run_chat_turn
from app.core.settings import settings
from app.schemas.case import CaseRecord

SAMPLE_CASE_PATH = Path("data/public/hermes_a_sample_case.json")


def _aliases() -> set[str]:
    raw = settings.telegram_bot_mentions or "Swain,Swain_SubAgent_bot"
    return {item.strip().lower().lstrip("@") for item in raw.split(",") if item.strip()}


def _sorted_aliases() -> list[str]:
    return sorted(_aliases(), key=len, reverse=True)


def _strip_addressed_mention(normalized: str) -> str | None:
    for alias in _sorted_aliases():
        prefix = re.compile(rf"^@{re.escape(alias)}(?=$|\s|[:,])[:,]?\s*", re.IGNORECASE)
        match = prefix.match(normalized)
        if match:
            return normalized[match.end() :].strip() or "/help"
    for alias in _sorted_aliases():
        inline = re.compile(rf"@{re.escape(alias)}(?=$|\s|[:,])", re.IGNORECASE)
        if inline.search(normalized):
            return " ".join(inline.sub("", normalized, count=1).split()) or "/help"
    return None


def extract_directed_text(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    aliases = set(_sorted_aliases())
    parts = normalized.split()
    first = parts[0]
    first_lower = first.lower()
    if first_lower.startswith("/") and "@" in first_lower:
        command, target = first_lower.split("@", 1)
        if target in aliases:
            return " ".join([command, *parts[1:]]).strip()
        return None
    mentioned = _strip_addressed_mention(normalized)
    if mentioned is not None:
        return mentioned
    for alias in _sorted_aliases():
        prefix = re.compile(rf"^{re.escape(alias)}\s*[:,]\s*", re.IGNORECASE)
        match = prefix.match(normalized)
        if match:
            return normalized[match.end() :].strip() or "/help"
    if first_lower.startswith("/"):
        return normalized
    return None

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


def handle_telegram_message(text: str) -> str | None:
    directed = extract_directed_text(text)
    if directed is None:
        return None
    normalized = directed.strip()
    lowered = normalized.lower()
    if lowered in {"/start", "start", "help", "/help"}:
        return (
            "Swain/Hermes A ready. Call me with @Swain or commands:\n"
            "/demo_a - run the sample post-audit case\n"
            "/case CASE-A-001 - show latest local case report\n"
            "/health - adapter health\n"
            "Natural-language questions route through Hermes; 9router is only a provider."
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
    return run_chat_turn(normalized).response_text


