# ruff: noqa
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Mapping

from .validators import parse_condition_prefix, required_token_score, sha256_text, static_validate, tokens
from .strict_audit import parserlike_static_audit


def _contract_val(contract: Mapping[str, Any], *names: str, default: str = "") -> str:
    for n in names:
        v = contract.get(n)
        if v is not None and str(v) and str(v).lower() != "nan":
            return str(v)
    return default


def _jaccard(a: list[str] | set[str], b: list[str] | set[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa | sb), 1)


@dataclass
class RewardV3Result:
    payload_text: str
    payload_stripped: str
    reward_total: float
    hard_gate_pass: bool
    r_ruleset: float
    r_cell: float
    r_required: float
    r_structure: float
    r_slot: float
    r_truth_condition: float
    r_diversity: float
    r_coverage: float
    r_length: float
    p_duplicate: float
    p_near_duplicate: float
    p_off_condition: float
    static_error_class: str
    root_adherence_valid: bool
    cell_adherence_valid: bool
    required_tokens_valid: bool
    contract_valid: bool
    parserlike_clean: bool
    parserlike_score: float
    parserlike_reasons: str
    parserlike_unknown_alpha_rate: float
    matched_root: str | None
    matched_cell: str | None
    reward_version: str = "reward_v3.1-strict-parserlike"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_payload_v3(
    text: str,
    contract: Mapping[str, Any],
    *,
    training_hashes: set[str] | None = None,
    recent_payloads: list[str] | None = None,
    coverage_count: int = 0,
    max_len: int = 256,
    reward_floor: float = 0.01,
) -> RewardV3Result:
    meta, stripped = parse_condition_prefix(text)
    if not stripped and not meta:
        stripped = str(text or "")
    target_root = _contract_val(contract, "root_grammar_id", "target_root_grammar")
    target_cell = _contract_val(contract, "structure_cell_id", "target_structure_cell")
    target_y = _contract_val(contract, "y_level")
    target_truth = bool(contract.get("expected_truth", contract.get("truth_variant", False)))

    gen_root = meta.get("ROOT")
    gen_cell = meta.get("CELL")
    gen_y = meta.get("Y")
    gen_truth_s = meta.get("TRUTH")
    gen_truth = None if gen_truth_s is None else gen_truth_s.upper() == "TRUE"

    # If the experiment uses raw generated payload without condition prefix, the contract is the source of truth.
    # Do not punish no-prefix text as off-ruleset in contract-constrained generation.
    if gen_root:
        r_ruleset = 1.0 if gen_root in {target_root, target_root.replace("PG_BOOL_", "")} or target_root.endswith(gen_root) else 0.0
        root_ok = r_ruleset == 1.0
    else:
        r_ruleset = 1.0
        root_ok = True
    if gen_cell:
        r_cell = 1.0 if gen_cell in {target_cell, target_cell.split("_")[-1]} or target_cell.endswith(gen_cell) else 0.0
        cell_ok = r_cell == 1.0
    else:
        r_cell = 1.0
        cell_ok = True
    if gen_y:
        y_ok = gen_y == target_y
    else:
        y_ok = True
    if gen_truth is None:
        r_truth = 1.0
    else:
        r_truth = 1.0 if gen_truth == target_truth else 0.0

    v = static_validate(stripped, contract)
    audit = parserlike_static_audit(stripped, repair_count=0, version="v4")
    r_required = required_token_score(stripped, contract.get("required_tokens", ""))
    # Blend the original contract/static score with parser-like grammar shape.
    # This makes high reward harder to obtain through permissive token matches alone.
    r_structure = 0.65 * float(v.static_score) + 0.35 * float(audit.score)
    r_slot = 1.0 if v.slot_sanity_valid else 0.0

    dup = 0.20 if training_hashes and sha256_text(stripped) in training_hashes else 0.0
    near_pen = 0.0
    diversity = 1.0
    if recent_payloads:
        cur = tokens(stripped)
        sims = [_jaccard(cur, tokens(parse_condition_prefix(x)[1] or x)) for x in recent_payloads[-512:]]
        mx = max(sims) if sims else 0.0
        diversity = max(0.0, 1.0 - mx)
        near_pen = 0.20 if mx >= 0.92 else 0.10 if mx >= 0.82 else 0.0
    coverage = 1.0 / math.sqrt(1.0 + max(0, int(coverage_count)))
    length = max(0.0, min(1.0, 1.0 - max(0, len(stripped) - max_len) / max(max_len, 1)))
    off_condition = 0.25 if not (root_ok and cell_ok and y_ok) else 0.0

    hard_gate = bool(
        v.delimiter_valid
        and v.quote_valid
        and v.parenthesis_valid
        and v.boolean_signal_valid
        and v.forbidden_tokens_valid
        and audit.clean
    )
    raw = (
        0.18 * r_ruleset
        + 0.15 * r_cell
        + 0.14 * r_required
        + 0.24 * r_structure
        + 0.08 * r_slot
        + 0.05 * r_truth
        + 0.05 * diversity
        + 0.04 * coverage
        + 0.02 * length
        - dup
        - near_pen
        - off_condition
        - (0.18 * (1.0 - float(audit.score)))
    )
    if not hard_gate:
        raw *= 0.25
    reward = max(float(reward_floor), min(1.0, raw))
    return RewardV3Result(
        payload_text=str(text or ""),
        payload_stripped=stripped,
        reward_total=round(float(reward), 6),
        hard_gate_pass=hard_gate,
        r_ruleset=round(float(r_ruleset), 6),
        r_cell=round(float(r_cell), 6),
        r_required=round(float(r_required), 6),
        r_structure=round(float(r_structure), 6),
        r_slot=round(float(r_slot), 6),
        r_truth_condition=round(float(r_truth), 6),
        r_diversity=round(float(diversity), 6),
        r_coverage=round(float(coverage), 6),
        r_length=round(float(length), 6),
        p_duplicate=round(float(dup), 6),
        p_near_duplicate=round(float(near_pen), 6),
        p_off_condition=round(float(off_condition), 6),
        static_error_class=v.error_class,
        root_adherence_valid=root_ok,
        cell_adherence_valid=cell_ok,
        required_tokens_valid=v.required_tokens_valid,
        contract_valid=bool(v.contract_valid and audit.clean),
        parserlike_clean=bool(audit.clean),
        parserlike_score=round(float(audit.score), 6),
        parserlike_reasons=";".join(audit.reasons),
        parserlike_unknown_alpha_rate=round(float(audit.unknown_alpha_rate), 6),
        matched_root=gen_root or target_root,
        matched_cell=gen_cell or target_cell,
    )
