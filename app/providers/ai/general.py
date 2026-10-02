import json

import httpx

from app.core.settings import settings


class GeneralAssistantProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None, timeout_seconds: float = 20.0) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    def answer(self, question: str) -> str:
        if not self.is_configured():
            return (
                "Swain chưa có AI_MODEL/AI_BASE_URL để trả lời natural-language. "
                "Các command hiện có: /demo_a, /case CASE-A-001, /health."
            )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Swain, the Hermes Telegram assistant. Be direct. "
                        "For current facts, rankings, prices, news, or wealth lists, say when live web/search sources are required. "
                        "Do not fabricate citations or pretend to have browsed. "
                        "Do not infer protected attributes such as race or ethnicity from names, faces, or nationality. "
                        "If a user asks for a ranking by race/ethnicity, explain the data limitation and offer a source-grounded alternative."
                    ),
                },
                {"role": "user", "content": question},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content.strip()[:3900]
            return "Swain nhận được phản hồi rỗng từ model."
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            return f"Swain AI route lỗi: {type(exc).__name__}. Core Hermes A vẫn chạy qua /demo_a."
