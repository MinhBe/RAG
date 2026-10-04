from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.core.text_normalize import fold_text

REPO_ROOT = Path(__file__).resolve().parents[2]
UNMATCHED_CASE_LOG = REPO_ROOT / ".omh" / "events" / "unmatched_cases.jsonl"

CaseId = Literal["local_place_lookup", "research_question", "generic"]

LOCAL_PLACE_PATTERNS = (
    "cau giay",
    "165 cau giay",
    "quan cat toc",
    "cat toc",
    "barber",
    "haircut",
    "salon",
    "gan day",
    "nearby",
    "near me",
    "dia chi",
    "address",
)
LOCAL_INTENT_PATTERNS = (
    "tim quan",
    "tim tiem",
    "tim dia diem",
    "tim cho",
    "lookup place",
    "find place",
    "local place",
)
RESEARCH_PATTERNS = (
    "nghien cuu",
    "research",
    "tim hieu",
    "tim thong tin",
    "so sanh nguon",
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
    "trich dan",
    "web",
)
GENERIC_PATTERNS = (
    "trien khai",
    "sua",
    "code",
    "build",
    "debug",
    "deploy",
    "test",
)


@dataclass(frozen=True)
class CaseMatch:
    case_id: CaseId
    confidence: float
    band: Literal["accept", "review", "fallback"]
    reasons: tuple[str, ...]


def _contains_any(folded_text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if pattern in folded_text]


def _band(score: float) -> Literal["accept", "review", "fallback"]:
    if score >= 0.8:
        return "accept"
    if score >= 0.5:
        return "review"
    return "fallback"


def match_case(user_text: str) -> CaseMatch:
    folded = fold_text(user_text)
    local_hits = _contains_any(folded, LOCAL_PLACE_PATTERNS)
    local_intent_hits = _contains_any(folded, LOCAL_INTENT_PATTERNS)
    local_location_hit = any(token in folded for token in ("cau giay", "165", "dia chi", "address"))
    if local_hits and (local_intent_hits or local_location_hit):
        score = min(0.74 + 0.10 * len(local_hits) + 0.08 * len(local_intent_hits), 0.97)
        reasons = tuple(f"local_place_keyword:{hit}" for hit in [*local_hits[:4], *local_intent_hits[:2]])
        return CaseMatch(
            case_id="local_place_lookup",
            confidence=round(score, 2),
            band=_band(score),
            reasons=reasons,
        )
    research_hits = _contains_any(folded, RESEARCH_PATTERNS)
    if research_hits:
        score = min(0.64 + 0.18 * len(research_hits), 0.94)
        return CaseMatch(
            case_id="research_question",
            confidence=round(score, 2),
            band=_band(score),
            reasons=tuple(f"research_keyword:{hit}" for hit in research_hits[:5]),
        )
    generic_hits = _contains_any(folded, GENERIC_PATTERNS)
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
