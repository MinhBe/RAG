import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.adapters.telegram import TelegramReply, handle_telegram_event
from app.core.settings import settings


@dataclass(frozen=True)
class BotConfig:
    username: str
    token: str


def _configured_bots() -> list[BotConfig]:
    candidates = [
        ("Swain_SubAgent_bot", settings.telegram_swain_bot_token or settings.telegram_bot_token),
        ("Shen_SubAgent_bot", settings.telegram_shen_bot_token),
        ("Garen_SubAgent_bot", settings.telegram_garen_bot_token),
        ("Kayn_SubAgent_bot", settings.telegram_kayn_bot_token),
    ]
    return [BotConfig(username=name, token=token) for name, token in candidates if token]


def _require_config() -> tuple[list[BotConfig], int]:
    bots = _configured_bots()
    if not bots:
        raise SystemExit("No Telegram bot tokens are configured")
    if not settings.telegram_allowed_chat_id:
        raise SystemExit("TELEGRAM_ALLOWED_CHAT_ID is not configured")
    return bots, int(settings.telegram_allowed_chat_id)


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_message(client: httpx.Client, bot: BotConfig, chat_id: int, text: str) -> None:
    client.post(
        _api_url(bot.token, "sendMessage"),
        json={"chat_id": chat_id, "text": text[:3900]},
        timeout=20.0,
    ).raise_for_status()


def _send_replies(
    client: httpx.Client,
    bots_by_username: dict[str, BotConfig],
    default_bot: BotConfig,
    chat_id: int,
    replies: list[TelegramReply],
) -> None:
    for reply in replies:
        sender = reply.sender_username or default_bot.username
        bot = bots_by_username.get(sender.lower())
        if bot is None:
            _send_message(
                client,
                default_bot,
                chat_id,
                f"Missing local token for @{sender}; cannot send this turn.",
            )
            time.sleep(0.45)
            continue
        _send_message(client, bot, chat_id, reply.text)
        time.sleep(0.45)


def _is_from_bot(message: dict[str, Any]) -> bool:
    sender = message.get("from") or {}
    return bool(sender.get("is_bot"))


def main() -> None:
    bots, allowed_chat_id = _require_config()
    bots_by_username = {bot.username.lower(): bot for bot in bots}
    offsets = {bot.username: 0 for bot in bots}
    configured_names = ", ".join(bot.username for bot in bots)
    print(f"Hermes Telegram multi-bot adapter started: {configured_names}. Tokens hidden.")
    with httpx.Client(timeout=35.0) as client:
        while True:
            for bot in bots:
                response = client.get(
                    _api_url(bot.token, "getUpdates"),
                    params={
                        "timeout": 1,
                        "offset": offsets[bot.username],
                        "allowed_updates": ["message"],
                    },
                )
                response.raise_for_status()
                updates: list[dict[str, Any]] = response.json().get("result", [])
                for update in updates:
                    offsets[bot.username] = max(
                        offsets[bot.username], int(update["update_id"]) + 1
                    )
                    message = update.get("message") or {}
                    if _is_from_bot(message):
                        continue
                    chat = message.get("chat") or {}
                    chat_id = int(chat.get("id", 0))
                    text = message.get("text") or ""
                    if chat_id != allowed_chat_id:
                        if chat_id:
                            _send_message(
                                client,
                                bot,
                                chat_id,
                                "Unauthorized chat_id for this Hermes demo.",
                            )
                        continue
                    try:
                        replies = handle_telegram_event(text, receiver_username=bot.username)
                    except (OSError, ValueError, ValidationError) as exc:
                        replies = [
                            TelegramReply(
                                sender_username=bot.username,
                                text=f"Hermes error: {type(exc).__name__}. Check local logs.",
                            )
                        ]
                    if replies:
                        _send_replies(client, bots_by_username, bot, chat_id, replies)
            time.sleep(0.2)


if __name__ == "__main__":
    main()
