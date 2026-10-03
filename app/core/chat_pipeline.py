from dataclasses import dataclass
from typing import Literal

from app.providers.ai.general import GeneralAssistantProvider


@dataclass(frozen=True)
class ChatTurnResult:
    response_text: str
    route: Literal["command", "general_llm", "fallback"]
    provider: str | None = None
    policy_notes: tuple[str, ...] = ()


def run_chat_turn(message: str, assistant_name: str = "Swain") -> ChatTurnResult:
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
    answer = GeneralAssistantProvider().answer(normalized, assistant_name=assistant_name)
    return ChatTurnResult(
        response_text=answer,
        route="general_llm",
        provider="9router_openai_compatible",
        policy_notes=("provider_is_not_orchestrator",),
    )
