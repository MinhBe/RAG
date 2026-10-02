import sys
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.adapters.telegram import handle_telegram_message
from app.core.settings import settings


def _require_config() -> tuple[str, str]:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured")
    if not settings.telegram_allowed_chat_id:
        raise SystemExit("TELEGRAM_ALLOWED_CHAT_ID is not configured")
    return settings.telegram_bot_token, settings.telegram_allowed_chat_id


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_message(client: httpx.Client, token: str, chat_id: int, text: str) -> None:
    client.post(
        _api_url(token, "sendMessage"),
        json={"chat_id": chat_id, "text": text[:3900]},
        timeout=20.0,
    ).raise_for_status()


def main() -> None:
    token, allowed_chat_id = _require_config()
    allowed = int(allowed_chat_id)
    offset = 0
    print("Hermes A Telegram adapter started. Authorized chat only. Token hidden.")
    with httpx.Client(timeout=35.0) as client:
        while True:
            response = client.get(
                _api_url(token, "getUpdates"),
                params={"timeout": 25, "offset": offset, "allowed_updates": ["message"]},
            )
            response.raise_for_status()
            updates: list[dict[str, Any]] = response.json().get("result", [])
            for update in updates:
                offset = max(offset, int(update["update_id"]) + 1)
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                chat_id = int(chat.get("id", 0))
                text = message.get("text") or ""
                if chat_id != allowed:
                    if chat_id:
                        _send_message(
                            client,
                            token,
                            chat_id,
                            "Unauthorized chat_id for this Hermes demo.",
                        )
                    continue
                try:
                    reply = handle_telegram_message(text)
                except (OSError, ValueError, ValidationError) as exc:
                    reply = f"Hermes A error: {type(exc).__name__}. Check local logs."
                _send_message(client, token, chat_id, reply)
            time.sleep(0.2)


if __name__ == "__main__":
    main()

