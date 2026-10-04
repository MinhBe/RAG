
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACE_ROOT = REPO_ROOT / ".omh" / "traces"


def append_trace_event(trace_id: str, event_type: str, payload: dict[str, Any]) -> Path:
    TRACE_ROOT.mkdir(parents=True, exist_ok=True)
    path = TRACE_ROOT / f"{trace_id}.jsonl"
    event = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "trace_id": trace_id,
        "event_type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path
