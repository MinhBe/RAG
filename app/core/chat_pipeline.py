from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.core.bot_personas import canonical_persona_name
from app.providers.ai.general import GeneralAssistantProvider


@dataclass(frozen=True)
class ChatTurnResult:
    response_text: str
    route: Literal["command", "general_llm", "fallback"]
    provider: str | None = None
    policy_notes: tuple[str, ...] = ()


_WORD_LIMIT_RE = re.compile(r"(?:\b(?:chỉ|chi|tối đa|toi da|dưới|duoi|limit)\b\s*)?(\d{1,3})\s*(?:chữ|chu|từ|tu|words?)", re.IGNORECASE)


def _requested_word_limit(message: str) -> int | None:
    match = _WORD_LIMIT_RE.search(message)
    if not match:
        return None
    limit = int(match.group(1))
    if 1 <= limit <= 120:
        return limit
    return None


def _trim_words(text: str, limit: int | None) -> str:
    if limit is None:
        return text.strip()
    words = text.strip().split()
    if len(words) <= limit:
        return text.strip()
    return " ".join(words[:limit]).rstrip(" ,;:")


def _strip_agent_labels(text: str, assistant_name: str, peer_names: tuple[str, ...]) -> str:
    own = canonical_persona_name(assistant_name)
    peer_set = {canonical_persona_name(peer).lower() for peer in peer_names if peer}
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        label_match = re.match(r"^([A-Za-z][A-Za-z0-9 ]{1,24})\s*[:ï¼š-]\s*(.*)$", line)
        if label_match:
            label = label_match.group(1).replace(" ", "").lower()
            body = label_match.group(2).strip()
            if label in peer_set:
                continue
            if label == own.lower():
                line = body
        lines.append(line)
    return "\n".join(lines).strip()


def run_chat_turn(
    message: str,
    assistant_name: str = "Swain",
    peer_names: tuple[str, ...] = (),
) -> ChatTurnResult:
    """Hermes chat entrypoint for UI/chat transports.

    Transport adapters must call this instead of invoking model providers
    directly. Providers such as 9router remain below Hermes core.
    """
    normalized = message.strip()
    if not normalized:
        return ChatTurnResult(
            response_text="Empty Hermes request.",
            route="fallback",
            provider=None,
            policy_notes=("empty_input",),
        )
    answer = GeneralAssistantProvider().answer(
        normalized,
        assistant_name=assistant_name,
        peer_names=peer_names,
    )
    answer = _strip_agent_labels(answer, assistant_name=assistant_name, peer_names=peer_names)
    answer = _trim_words(answer, _requested_word_limit(normalized))
    return ChatTurnResult(
        response_text=answer,
        route="general_llm",
        provider="9router_openai_compatible",
        policy_notes=("provider_is_not_orchestrator",),
    )

