import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.omh_hooks import omh_runtime_status_text

if __name__ == "__main__":
    print(omh_runtime_status_text())
