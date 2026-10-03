import os
import random
import re
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


CHAT_ACTION_DELAY_MIN_SECONDS = 0.45
CHAT_ACTION_DELAY_MAX_SECONDS = 0.95
POST_SEND_DELAY_SECONDS = 0.35


def _local_env_values() -> dict[str, str]:
    values = dict(os.environ)
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            values.setdefault(key, value)
    return values


def _token_key_for_username(username: str) -> str:
    short = username.strip().lstrip("@").split("_", 1)[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", short).upper().strip("_")
    return f"TELEGRAM_{slug}_BOT_TOKEN"


def _configured_bots() -> list[BotConfig]:
    env_values = _local_env_values()
    raw_names = env_values.get("TELEGRAM_BOT_USERNAMES") or settings.telegram_bot_usernames
    usernames = [item.strip().lstrip("@") for item in raw_names.split(",") if item.strip()]
    bots: list[BotConfig] = []
    for username in dict.fromkeys(usernames):
        token = env_values.get(_token_key_for_username(username))
        if username.lower() == "swain_subagent_bot":
            token = token or env_values.get("TELEGRAM_BOT_TOKEN")
        if token:
            bots.append(BotConfig(username=username, token=token))
    return bots


def _require_config() -> tuple[list[BotConfig], int]:
    bots = _configured_bots()
    if not bots:
        raise SystemExit("No Telegram bot tokens are configured")
    if not settings.telegram_allowed_chat_id:
        raise SystemExit("TELEGRAM_ALLOWED_CHAT_ID is not configured")
    return bots, int(settings.telegram_allowed_chat_id)


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _show_processing_action(client: httpx.Client, bot: BotConfig, chat_id: int) -> None:
    try:
        client.post(
            _api_url(bot.token, "sendChatAction"),
            json={"chat_id": chat_id, "action": "typing"},
            timeout=10.0,
        ).raise_for_status()
    except httpx.HTTPError as exc:
        print(
            f"Telegram chat action error for @{bot.username}: {type(exc).__name__}",
            flush=True,
        )


def _response_delay_seconds(text: str) -> float:
    length_factor = min(len(text) / 220.0, 0.55)
    base = random.uniform(CHAT_ACTION_DELAY_MIN_SECONDS, CHAT_ACTION_DELAY_MAX_SECONDS)
    return min(base + length_factor, 1.45)


def _send_message(client: httpx.Client, bot: BotConfig, chat_id: int, text: str) -> None:
    _show_processing_action(client, bot, chat_id)
    time.sleep(_response_delay_seconds(text))
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
            time.sleep(POST_SEND_DELAY_SECONDS)
            continue
        _send_message(client, bot, chat_id, reply.text)
        time.sleep(POST_SEND_DELAY_SECONDS)


def _is_from_bot(message: dict[str, Any]) -> bool:
    sender = message.get("from") or {}
    return bool(sender.get("is_bot"))


def main() -> None:
    bots, allowed_chat_id = _require_config()
    bots_by_username = {bot.username.lower(): bot for bot in bots}
    offsets = {bot.username: 0 for bot in bots}
    configured_names = ", ".join(bot.username for bot in bots)
    print(
        f"Hermes Telegram multi-bot adapter started: {configured_names}. Tokens hidden.",
        flush=True,
    )
    with httpx.Client(timeout=35.0) as client:
        while True:
            for bot in bots:
                try:
                    response = client.get(
                        _api_url(bot.token, "getUpdates"),
                        params={
                            "timeout": 1,
                            "offset": offsets[bot.username],
                            "allowed_updates": '["message"]',
                        },
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    print(f"Telegram polling error for @{bot.username}: HTTP {status}", flush=True)
                    time.sleep(2.0)
                    continue
                except httpx.HTTPError as exc:
                    print(
                        f"Telegram polling error for @{bot.username}: {type(exc).__name__}",
                        flush=True,
                    )
                    time.sleep(2.0)
                    continue
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
                    chat_type = str(chat.get("type") or "")
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
                    print(
                        f"Telegram update for @{bot.username}: chat_type={chat_type} "
                        f"text_len={len(text)} replies={len(replies)}",
                        flush=True,
                    )
                    if replies:
                        _send_replies(client, bots_by_username, bot, chat_id, replies)
            time.sleep(0.2)


if __name__ == "__main__":
    main()


