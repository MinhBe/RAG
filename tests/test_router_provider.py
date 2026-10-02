import httpx
import pytest

from app.providers.ai.router import RouterProvider


@pytest.mark.asyncio
async def test_router_status_is_structured_and_secret_free():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "list", "data": []})

    provider = RouterProvider(transport=httpx.MockTransport(handler))
    status = await provider.status()
    assert status["reachable"] is True
    assert status["http_status"] == 200
    assert status["gateway_ready"] is True
    assert "Authorization" not in str(status)
