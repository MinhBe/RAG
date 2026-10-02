import httpx

from app.core.settings import settings


class RouterProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = settings.ai_base_url.rstrip("/")
        self.transport = transport

    async def status(self) -> dict:
        headers = {}
        if settings.ai_api_key:
            headers["Authorization"] = f"Bearer {settings.ai_api_key}"
        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self.transport) as client:
                response = await client.get(f"{self.base_url}/models", headers=headers)
            return {
                "reachable": True,
                "http_status": response.status_code,
                "gateway_ready": response.status_code < 500,
                "api_key_configured": bool(settings.ai_api_key),
                "model_configured": bool(settings.ai_model),
            }
        except httpx.HTTPError as exc:
            return {
                "reachable": False,
                "http_status": None,
                "gateway_ready": False,
                "api_key_configured": bool(settings.ai_api_key),
                "model_configured": bool(settings.ai_model),
                "error_type": type(exc).__name__,
            }

    async def health(self) -> bool:
        return bool((await self.status())["gateway_ready"])
