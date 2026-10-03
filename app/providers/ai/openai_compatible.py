import json
from typing import Any

import httpx


def _extract_from_choice(choice: dict[str, Any]) -> str:
    message = choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    delta = choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    return ""


def extract_chat_content(response: httpx.Response) -> str:
    """Extract assistant content from OpenAI-compatible JSON or SSE responses."""
    content_type = response.headers.get("content-type", "").lower()
    text = response.text

    if "text/event-stream" in content_type or text.lstrip().startswith("data:"):
        parts: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data or data == "[DONE]":
                continue
            chunk = json.loads(data)
            choices = chunk.get("choices", [])
            if choices and isinstance(choices[0], dict):
                parts.append(_extract_from_choice(choices[0]))
        return "".join(parts)

    body = response.json()
    choices = body["choices"]
    if not choices or not isinstance(choices[0], dict):
        return ""
    return _extract_from_choice(choices[0])
