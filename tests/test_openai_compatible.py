import httpx

from app.providers.ai.openai_compatible import extract_chat_content


def test_extract_chat_content_from_json_response():
    response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "plain json"}}]},
    )
    assert extract_chat_content(response) == "plain json"


def test_extract_chat_content_from_sse_response():
    response = httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text=(
            'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"O"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"K"}}]}\n\n'
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        ),
    )
    assert extract_chat_content(response) == "OK"
