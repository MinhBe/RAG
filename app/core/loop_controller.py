
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class LoopPolicy:
    max_rounds: int = 5
    max_cost_units: float = 10.0
    deadline_at: datetime | None = None
    no_improvement_rounds: int = 2


@dataclass(frozen=True)
class LoopObservation:
    round_index: int
    score: float
    cost_units: float = 0.0


@dataclass(frozen=True)
class LoopDecision:
    continue_loop: bool
    reason: str


def _score_has_not_improved(history: list[LoopObservation], window: int) -> bool:
    if len(history) <= window:
        return False
    recent = history[-window:]
    previous_best = max(item.score for item in history[:-window])
    recent_best = max(item.score for item in recent)
    return recent_best <= previous_best


def decide_loop(policy: LoopPolicy, history: list[LoopObservation], now: datetime | None = None) -> LoopDecision:
    now = now or datetime.now(UTC)
    if len(history) >= policy.max_rounds:
        return LoopDecision(False, "max_rounds_reached")
    if sum(item.cost_units for item in history) >= policy.max_cost_units:
        return LoopDecision(False, "budget_exhausted")
    if policy.deadline_at is not None and now >= policy.deadline_at:
        return LoopDecision(False, "deadline_reached")
    if _score_has_not_improved(history, policy.no_improvement_rounds):
        return LoopDecision(False, "score_not_improving")
    return LoopDecision(True, "continue")
