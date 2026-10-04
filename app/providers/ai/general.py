import json

import httpx

from app.core.bot_personas import build_persona_prompt, canonical_persona_name
from app.core.settings import settings
from app.providers.ai.openai_compatible import extract_chat_content


class GeneralAssistantProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None, timeout_seconds: float = 20.0) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def answer(
        self,
        question: str,
        assistant_name: str = "Swain",
        peer_names: tuple[str, ...] = (),
        system_context: tuple[str, ...] = (),
    ) -> str:
        if not self.is_configured():
            return (
                f"{canonical_persona_name(assistant_name)} chưa có AI_MODEL/AI_BASE_URL để trả lời natural-language. "
                "Các command hiện có: /demo_a, /case CASE-A-001, /health."
            )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        system_prompt = build_persona_prompt(assistant_name, peer_names=peer_names)
        if system_context:
            system_prompt = system_prompt + "\n\n" + "\n\n".join(part for part in system_context if part)
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": question},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            content = extract_chat_content(response)
            if isinstance(content, str) and content.strip():
                return content.strip()[:3900]
            return f"{canonical_persona_name(assistant_name)} nhận được phản hồi rỗng từ model."
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            return f"{canonical_persona_name(assistant_name)} AI route lỗi: {type(exc).__name__}. Core Hermes A vẫn chạy qua /demo_a."
