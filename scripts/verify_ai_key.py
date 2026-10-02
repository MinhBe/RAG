import os

import httpx
from dotenv import load_dotenv

load_dotenv()
base = os.environ["AI_BASE_URL"].rstrip("/")
api_key = os.environ.get("AI_API_KEY", "")
model = os.environ.get("AI_MODEL", "")
print("ai_key_configured", bool(api_key))
print("model_configured", bool(model))
print("model", model)
headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
with httpx.Client(timeout=30.0) as client:
    models = client.get(f"{base}/models", headers=headers)
    print("models_status", models.status_code)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "temperature": 0,
        "max_tokens": 8,
    }
    response = client.post(f"{base}/chat/completions", headers=headers, json=payload)
    print("completion_status", response.status_code)
