
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
UNMATCHED_CASE_LOG = REPO_ROOT / ".omh" / "events" / "unmatched_cases.jsonl"

CaseId = Literal["research_question", "generic"]

RESEARCH_PATTERNS = (
    "nghiÃªn cá»©u",
    "nghien cuu",
    "research",
    "tÃ¬m hiá»ƒu",
    "tim hieu",
    "tÃ¬m thÃ´ng tin",
    "tim thong tin",
    "so sÃ¡nh nguá»“n",
    "so sanh nguon",
    "bÃ¡o cÃ¡o",
    "bao cao",
    "citation",
    "citations",
    "cite",
    "sources",
    "source synthesis",
    "find information",
    "compare sources",
    "rank sources",
    "report",
    "trÃ­ch dáº«n",
    "trich dan",
    "web",
)
GENERIC_PATTERNS = (
    "triá»ƒn khai",
    "trien khai",
    "sá»­a",
    "sua",
    "code",
    "build",
    "debug",
)


@dataclass(frozen=True)
class CaseMatch:
    case_id: CaseId
    confidence: float
    band: Literal["accept", "review", "fallback"]
    reasons: tuple[str, ...]


def _contains_any(text: str, patterns: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern in lowered]


def match_case(user_text: str) -> CaseMatch:
    research_hits = _contains_any(user_text, RESEARCH_PATTERNS)
    generic_hits = _contains_any(user_text, GENERIC_PATTERNS)
    if research_hits:
        score = min(0.64 + 0.18 * len(research_hits), 0.94)
        band = "accept" if score >= 0.8 else "review"
        return CaseMatch(
            case_id="research_question",
            confidence=round(score, 2),
            band=band,
            reasons=tuple(f"research_keyword:{hit}" for hit in research_hits[:5]),
        )
    if generic_hits:
        return CaseMatch(
            case_id="generic",
            confidence=0.55,
            band="review",
            reasons=tuple(f"generic_keyword:{hit}" for hit in generic_hits[:5]),
        )
    return CaseMatch(
        case_id="generic",
        confidence=0.0,
        band="fallback",
        reasons=("no case-specific pattern reached threshold",),
    )


def should_record_unmatched(match: CaseMatch) -> bool:
    return match.case_id == "generic" and match.confidence < 0.5


def record_unmatched_case(user_text: str, match: CaseMatch, trace_id: str | None = None) -> None:
    if not should_record_unmatched(match):
        return
    UNMATCHED_CASE_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "trace_id": trace_id,
        "user_text": user_text,
        "case_id": match.case_id,
        "confidence": match.confidence,
        "reasons": list(match.reasons),
    }
    with UNMATCHED_CASE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
