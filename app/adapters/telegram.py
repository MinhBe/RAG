import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.case_pipeline import run_case_pipeline
from app.core.chat_pipeline import run_chat_turn
from app.core.omh_hooks import handle_omh_command
from app.core.orchestration import (
    create_intake_job,
    is_user_override_request,
    should_async_intake,
)
from app.core.runtime_guard import evaluate_runtime_request_for_username
from app.core.settings import settings
from app.core.skill_registry import (
    bot_id_for_telegram_username,
    format_all_bot_skill_matrix,
    format_bot_identity,
    format_skill_resolution_for_username,
)
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


def short_bot_name(username: str) -> str:
    return username.strip().lstrip("@").split("_", 1)[0]


def _full_aliases(receiver_username: str | None = None) -> set[str]:
    if receiver_username:
        return {receiver_username.lower().lstrip("@")}
    return {item.lower() for item in configured_bot_usernames()}


def _short_aliases(receiver_username: str | None = None) -> set[str]:
    if receiver_username:
        return {short_bot_name(receiver_username).lower()}
    return {short_bot_name(item).lower() for item in configured_bot_usernames()}


def _sorted_full_aliases(receiver_username: str | None = None) -> list[str]:
    return sorted(_full_aliases(receiver_username), key=len, reverse=True)


def _sorted_short_aliases(receiver_username: str | None = None) -> list[str]:
    return sorted(_short_aliases(receiver_username), key=len, reverse=True)


def _strip_addressed_mention(normalized: str, receiver_username: str | None = None) -> str | None:
    for alias in _sorted_full_aliases(receiver_username):
        prefix = re.compile(rf"^@{re.escape(alias)}(?=$|\s|[:,])[:,]?\s*", re.IGNORECASE)
        match = prefix.match(normalized)
        if match:
            return normalized[match.end() :].strip() or "/help"
    for alias in _sorted_full_aliases(receiver_username):
        inline = re.compile(rf"@{re.escape(alias)}(?=$|\s|[:,])", re.IGNORECASE)
        if inline.search(normalized):
            return " ".join(inline.sub("", normalized, count=1).split()) or "/help"
    return None


def _strip_addressed_short_name(normalized: str, receiver_username: str | None = None) -> str | None:
    for alias in _sorted_short_aliases(receiver_username):
        prefix = re.compile(rf"^{re.escape(alias)}(?=$|\s|[:,])[:,]?\s*", re.IGNORECASE)
        match = prefix.match(normalized)
        if match:
            return normalized[match.end() :].strip() or "/help"
    return None



def _line_addresses_any_bot(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    first = stripped.split()[0].lower()
    if first.startswith('/') and '@' in first:
        _, target = first.split('@', 1)
        if target in {name.lower() for name in configured_bot_usernames()}:
            return True
    for username in configured_bot_usernames():
        if re.search(rf"@{re.escape(username)}(?=$|\s|[:,])", stripped, flags=re.IGNORECASE):
            return True
    first_clean = first.rstrip(':,')
    short_aliases = {short_bot_name(name).lower() for name in configured_bot_usernames()}
    return first_clean.lstrip('@') in short_aliases and (first_clean.startswith('@') or first_clean in short_aliases)


def _is_lead_receiver(receiver_username: str | None) -> bool:
    if receiver_username is None:
        return True
    return bot_id_for_telegram_username(receiver_username) == "lead"


def _extract_directed_text_single(normalized: str, receiver_username: str | None = None) -> str | None:
    if not normalized:
        return None
    aliases = set(_sorted_full_aliases(receiver_username))
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
    short_named = _strip_addressed_short_name(normalized, receiver_username)
    if short_named is not None:
        return short_named
    if first_lower.startswith("/") and receiver_username is None:
        return normalized
    return None


def extract_directed_text(text: str, receiver_username: str | None = None) -> str | None:
    """Return only the message segments meant for this receiver.

    Routing is line-scoped. A line addressed to @Lucian is invisible to Swain.
    A line with no explicit bot address goes only to Lead/the DM context.
    """
    normalized = text.strip()
    if not normalized:
        return None
    segments: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        directed = _extract_directed_text_single(line, receiver_username=receiver_username)
        if directed is not None:
            segments.append(directed)
            continue
        if not _line_addresses_any_bot(line) and _is_lead_receiver(receiver_username):
            segments.append(line)
    if segments:
        return "\n".join(segments).strip()
    return None

def addressed_bot_usernames(text: str) -> list[str]:
    normalized = text.strip()
    found: list[tuple[int, str]] = []
    for username in configured_bot_usernames():
        pattern = re.compile(rf"@{re.escape(username)}(?=$|\s|[:,])", re.IGNORECASE)
        match = pattern.search(normalized)
        if match:
            found.append((match.start(), username))
    return [username for _, username in sorted(found, key=lambda item: item[0])]


def strip_all_bot_mentions(text: str) -> str:
    cleaned = text
    for username in configured_bot_usernames():
        cleaned = re.sub(rf"@{re.escape(username)}(?=$|\s|[:,])[:,]?\s*", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


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
    lines = ["Hermes Telegram adapter ready. Address a bot with short name or full username:"]
    for name in configured_bot_usernames():
        lines.append(f"- {short_bot_name(name)} or @{name}")
    lines.extend(
        [
            "Commands:",
            "/demo_a - run the sample post-audit case",
            "/case CASE-A-001 - show latest local case report",
            "/chain eye - run a 50-turn English word chain across all four bots",
            "/health - adapter health",
            "/omh - Oh My Hermes deployment status",
            "/skills - skills allowed for the current bot profile",
            "/whoami - current bot profile and permission ceiling",
            "/skills-all - bot/skill access matrix",
            "Natural-language questions route through Hermes; 9router is only a provider.",
        ]
    )
    return "\n".join(lines)


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


COMMAND_TOKEN_RE = re.compile(r"/(?:skills-all|whoami|skills|health)\b", re.IGNORECASE)


def _single_deterministic_command_reply(command: str, sender: str | None) -> TelegramReply | None:
    lowered = command.lower().strip()
    if lowered == "/health":
        return TelegramReply(sender, "Hermes Telegram adapter: ok")
    if lowered == "/whoami":
        bot_id = bot_id_for_telegram_username(sender)
        if bot_id is None:
            return TelegramReply(sender, "No Hermes bot profile is mapped to this Telegram username.")
        return TelegramReply(sender, format_bot_identity(bot_id))
    if lowered == "/skills":
        return TelegramReply(sender, format_skill_resolution_for_username(sender))
    if lowered == "/skills-all":
        return TelegramReply(sender, format_all_bot_skill_matrix())
    return None


def _deterministic_command_replies(normalized: str, sender: str | None) -> list[TelegramReply] | None:
    matches = list(COMMAND_TOKEN_RE.finditer(normalized))
    if not matches:
        return None
    # If any slash command is present, handle recognized deterministic commands here and do not let LLM rephrase them.
    replies: list[TelegramReply] = []
    for match in matches:
        reply = _single_deterministic_command_reply(match.group(0), sender)
        if reply is not None:
            replies.append(reply)
    return replies or None


def handle_telegram_event(
    text: str,
    receiver_username: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> list[TelegramReply]:
    directed = extract_directed_text(text, receiver_username=receiver_username)
    if directed is None:
        return []
    normalized = directed.strip()
    lowered = normalized.lower()
    sender = receiver_username
    if lowered in {"/start", "start", "help", "/help"}:
        return [TelegramReply(sender, _help_text())]
    command_replies = _deterministic_command_replies(normalized, sender)
    if command_replies is not None:
        return command_replies
    if lowered == "/health":
        return [TelegramReply(sender, "Hermes Telegram adapter: ok")]
    if lowered in {"/whoami", "whoami"}:
        bot_id = bot_id_for_telegram_username(sender)
        if bot_id is None:
            return [TelegramReply(sender, "No Hermes bot profile is mapped to this Telegram username.")]
        return [TelegramReply(sender, format_bot_identity(bot_id))]
    if lowered in {"/skills", "skills", "skill inventory"}:
        return [TelegramReply(sender, format_skill_resolution_for_username(sender))]
    if lowered in {"/skills-all", "skills-all", "skill matrix"}:
        return [TelegramReply(sender, format_all_bot_skill_matrix())]
    if lowered == "oh my hermes" or lowered == "omh" or lowered.startswith("/omh"):
        return [TelegramReply(sender, handle_omh_command(normalized))]
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
            target_length=50,
        )
        return [_render_chain_turn(turn) for turn in turns]
    guard = evaluate_runtime_request_for_username(sender, normalized)
    if guard is not None:
        return [TelegramReply(sender, guard.message)]
    bot_id = bot_id_for_telegram_username(sender)
    if sender is not None and bot_id is None:
        return [TelegramReply(sender, "BLOCKED by Hermes runtime profile guard: no bot profile is mapped to this Telegram username.")]
    intake_prompt = strip_all_bot_mentions(normalized) or normalized
    if should_async_intake(intake_prompt, bot_id):
        ack = create_intake_job(
            intake_prompt,
            user_override=is_user_override_request(intake_prompt),
            chat_id=chat_id,
            message_id=message_id,
        )
        return [TelegramReply(sender, ack.text)]
    assistant_name = short_bot_name(sender or configured_bot_usernames()[0])
    addressed = addressed_bot_usernames(text)
    peer_names = tuple(
        short_bot_name(username)
        for username in addressed
        if sender is None or username.lower() != sender.lower()
    )
    llm_prompt = strip_all_bot_mentions(normalized) or normalized
    try:
        chat_result = run_chat_turn(
            llm_prompt,
            assistant_name=assistant_name,
            peer_names=peer_names,
            bot_id=bot_id,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        chat_result = run_chat_turn(
            llm_prompt,
            assistant_name=assistant_name,
            peer_names=peer_names,
        )
    return [TelegramReply(sender, chat_result.response_text)]


def handle_telegram_message(text: str, receiver_username: str | None = None) -> str | None:
    replies = handle_telegram_event(text, receiver_username=receiver_username)
    return replies[0].text if replies else None
