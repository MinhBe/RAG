from __future__ import annotations

from dataclasses import dataclass

DISALLOWED_LITERAL_FRAGMENTS = (
    "http://",
    "https://",
    "127.0.0.1",
    "localhost",
    "curl ",
    "powershell",
    "cmd.exe",
    "wget ",
)


@dataclass(frozen=True)
class SafetyReport:
    accepted: bool
    reason: str


def validate_symbolic_sequence(line: str) -> SafetyReport:
    stripped = line.strip()
    if not stripped:
        return SafetyReport(False, "empty")
    lowered = stripped.lower()
    for fragment in DISALLOWED_LITERAL_FRAGMENTS:
        if fragment in lowered:
            return SafetyReport(False, f"disallowed fragment: {fragment}")
    if len(stripped) > 512:
        return SafetyReport(False, "line too long")
    return SafetyReport(True, "accepted")
