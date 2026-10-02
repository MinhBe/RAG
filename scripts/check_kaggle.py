import json
from pathlib import Path

TOKEN_PATH = Path.home() / ".kaggle" / "kaggle.json"


def main() -> None:
    print("token_path_exists=", TOKEN_PATH.exists())
    if not TOKEN_PATH.exists():
        print("kaggle_ready= False")
        return
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8-sig"))
    username = str(data.get("username", "")).strip()
    key = str(data.get("key", "")).strip()
    print("username_configured=", bool(username))
    print("key_configured=", bool(key))
    print("key_length_gt_20=", len(key) > 20)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        print("kaggle_package_available= False")
        print("import_error_type=", type(exc).__name__)
        print("kaggle_ready= False")
        return
    api = KaggleApi()
    try:
        api.authenticate()
        print("kaggle_authenticate= True")
        print("kaggle_ready= True")
    except (OSError, RuntimeError, ValueError) as exc:
        print("kaggle_authenticate= False")
        print("auth_error_type=", type(exc).__name__)
        print("kaggle_ready= False")


if __name__ == "__main__":
    main()
