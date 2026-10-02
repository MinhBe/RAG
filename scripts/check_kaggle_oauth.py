import json
from pathlib import Path

home = Path.home()
paths = [
    home / ".kaggle" / "credentials.json",
    home / ".kaggle" / "access_token",
]

for path in paths:
    print(f"path={path}")
    print(f"exists={path.exists()}")
    if not path.exists():
        continue
    print(f"size={path.stat().st_size}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"json_parse=False error={type(exc).__name__}")
        continue
    print("json_parse=True")
    print("top_level_keys=", sorted(data.keys()))
    for key, value in data.items():
        if isinstance(value, str):
            print(f"{key}_string_length={len(value)}")
        elif isinstance(value, dict):
            print(f"{key}_dict_keys={sorted(value.keys())}")
