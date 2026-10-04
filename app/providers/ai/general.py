import json
import time

import httpx

from app.core.bot_personas import build_persona_prompt, canonical_persona_name
from app.core.settings import settings
from app.providers.ai.openai_compatible import extract_chat_content


class GeneralAssistantProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.transport = transport
        self.timeout_seconds = timeout_seconds or settings.ai_timeout_seconds
        self.retry_count = max(settings.ai_retry_count, 0)

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
        attempts = self.retry_count + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                    response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                content = extract_chat_content(response)
                if isinstance(content, str) and content.strip():
                    return content.strip()[:3900]
                return f"{canonical_persona_name(assistant_name)} nhận được phản hồi rỗng từ model."
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(0.8 * (attempt + 1))
                    continue
            except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                last_error = exc
                break
        error_name = type(last_error).__name__ if last_error else "UnknownError"
        return (
            f"{canonical_persona_name(assistant_name)} AI route chậm hoặc lỗi: {error_name}. "
            "Phiên vẫn sống. Hãy thử lại ngắn hơn hoặc dùng lệnh nội bộ: /omh, /skills, /health."
        )
