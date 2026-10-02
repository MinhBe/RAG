import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.case_pipeline import run_case_pipeline
from app.core.chat_pipeline import run_chat_turn
from app.core.settings import settings
from app.core.word_chain_game import WordChainTurn, build_word_chain
from app.schemas.case import CaseRecord

SAMPLE_CASE_PATH = Path("data/public/hermes_a_sample_case.json")
DEFAULT_BOT_USERNAMES = (
    "Swain_SubAgent_bot",
    "Shen_SubAgent_bot",
    "Garen_SubAgent_bot",
    "Kayn_SubAgent_bot",
)


@dataclass(frozen=True)
class TelegramReply:
    sender_username: str | None
    text: str


def configured_bot_usernames() -> list[str]:
    raw = settings.telegram_bot_usernames or ",".join(DEFAULT_BOT_USERNAMES)
    return [item.strip().lstrip("@") for item in raw.split(",") if item.strip()]


def _aliases(receiver_username: str | None = None) -> set[str]:
    if receiver_username:
        return {receiver_username.lower().lstrip("@")}
    return {item.lower() for item in configured_bot_usernames()}


def _sorted_aliases(receiver_username: str | None = None) -> list[str]:
    return sorted(_aliases(receiver_username), key=len, reverse=True)


def _strip_addressed_mention(normalized: str, receiver_username: str | None = None) -> str | None:
    for alias in _sorted_aliases(receiver_username):
        prefix = re.compile(rf"^@{re.escape(alias)}(?=$|\s|[:,])[:,]?\s*", re.IGNORECASE)
        match = prefix.match(normalized)
        if match:
            return normalized[match.end() :].strip() or "/help"
    for alias in _sorted_aliases(receiver_username):
        inline = re.compile(rf"@{re.escape(alias)}(?=$|\s|[:,])", re.IGNORECASE)
        if inline.search(normalized):
            return " ".join(inline.sub("", normalized, count=1).split()) or "/help"
    return None


def extract_directed_text(text: str, receiver_username: str | None = None) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    aliases = set(_sorted_aliases(receiver_username))
    parts = normalized.split()
    first = parts[0]
    first_lower = first.lower()
    if first_lower.startswith("/") and "@" in first_lower:
        command, target = first_lower.split("@", 1)
        if target in aliases:
            return " ".join([command, *parts[1:]]).strip()
        return None
    mentioned = _strip_addressed_mention(normalized, receiver_username)
    if mentioned is not None:
        return mentioned
    if first_lower.startswith("/") and receiver_username is None:
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


def _help_text() -> str:
    mentions = ", ".join(f"@{name}" for name in configured_bot_usernames())
    return (
        "Hermes Telegram adapter ready. Use full bot usernames only:\n"
        f"{mentions}\n"
        "Commands:\n"
        "/demo_a - run the sample post-audit case\n"
        "/case CASE-A-001 - show latest local case report\n"
        "/chain apple - run a 10-turn English word chain across all four bots\n"
        "/health - adapter health\n"
        "Natural-language questions route through Hermes; 9router is only a provider."
    )


def _extract_chain_start_word(normalized: str) -> str | None:
    lowered = normalized.lower().strip()
    for prefix in ("/chain", "chain", "wordchain", "word chain", "nối từ", "noi tu"):
        if lowered == prefix:
            return None
        if lowered.startswith(prefix + " "):
            return normalized[len(prefix) :].strip() or None
    return None


def _is_chain_request(normalized: str) -> bool:
    lowered = normalized.lower().strip()
    return lowered in {"/chain", "chain", "wordchain", "word chain", "nối từ", "noi tu"} or any(
        lowered.startswith(prefix + " ")
        for prefix in ("/chain", "chain", "wordchain", "word chain", "nối từ", "noi tu")
    )


def _render_chain_turn(turn: WordChainTurn) -> TelegramReply:
    return TelegramReply(sender_username=turn.bot_username, text=turn.render())


def handle_telegram_event(text: str, receiver_username: str | None = None) -> list[TelegramReply]:
    directed = extract_directed_text(text, receiver_username=receiver_username)
    if directed is None:
        return []
    normalized = directed.strip()
    lowered = normalized.lower()
    sender = receiver_username
    if lowered in {"/start", "start", "help", "/help"}:
        return [TelegramReply(sender, _help_text())]
    if lowered == "/health":
        return [TelegramReply(sender, "Hermes Telegram adapter: ok")]
    if lowered in {"/demo_a", "demo_a", "demo a"}:
        payload = json.loads(SAMPLE_CASE_PATH.read_text(encoding="utf-8-sig"))
        case = CaseRecord.model_validate(payload["case"])
        report = run_case_pipeline(case)
        return [TelegramReply(sender, format_case_report(report))]
    if lowered.startswith(("/case", "case ")):
        parts = normalized.split()
        if len(parts) != 2:
            return [TelegramReply(sender, "Usage: /case CASE-A-001")]
        case_id = parts[1]
        report = _load_latest_case_report(case_id)
        if report is None:
            return [TelegramReply(sender, f"No local report found for {case_id}. Run /demo_a first.")]
        return [TelegramReply(sender, format_case_report(report))]
    if _is_chain_request(normalized):
        start_word = _extract_chain_start_word(normalized)
        start_bot = receiver_username or configured_bot_usernames()[0]
        turns = build_word_chain(
            start_bot_username=start_bot,
            bot_usernames=configured_bot_usernames(),
            start_word=start_word,
            target_length=10,
        )
        return [_render_chain_turn(turn) for turn in turns]
    return [TelegramReply(sender, run_chat_turn(normalized).response_text)]


def handle_telegram_message(text: str, receiver_username: str | None = None) -> str | None:
    replies = handle_telegram_event(text, receiver_username=receiver_username)
    return replies[0].text if replies else None
