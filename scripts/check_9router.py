import httpx

base = "http://127.0.0.1:20128"
for path in ("/", "/v1/models"):
    try:
        response = httpx.get(base + path, timeout=5.0)
        print(path, response.status_code, response.text[:300].replace("\n", " "))
    except httpx.HTTPError as exc:
        print(path, "ERROR", type(exc).__name__, str(exc))
