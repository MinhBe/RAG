from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

TOKEN_RE = re.compile(r"BETWEEN|AND|<>|!=|<=|>=|=|<|>|\d+(?:\.\d+)?|[()+\-*/]", re.IGNORECASE)
ALLOWED_EXPR_RE = re.compile(r"^[0-9A-Za-z_\s().+\-*/<>=!]+$")
BLOCKED_WORDS = ("select", "insert", "update", "delete", "drop", "union", "from", "where", "sleep", "pg_", "copy")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def normalize_expr(expr: str) -> str:
    normalized = " ".join(expr.strip().split())
    normalized = re.sub(r"\s*<>\s*", " <> ", normalized)
    normalized = re.sub(r"\s*(<=|>=|!=|=|<|>)\s*", r" \1 ", normalized)
    normalized = re.sub(r"\s*([()+\-*/])\s*", r" \1 ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def token_classes(expr: str) -> list[str]:
    classes: list[str] = []
    for token in TOKEN_RE.findall(expr):
        upper = token.upper()
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            classes.append("NUM_DECIMAL" if "." in token else "NUM_INT")
        elif upper in {"BETWEEN", "AND"}:
            classes.append(f"KW_{upper}")
        elif token in {"=", "<>", "!=", "<", ">", "<=", ">="}:
            classes.append("OP_COMPARE")
        elif token in {"+", "-", "*", "/"}:
            classes.append("OP_ARITH")
        elif token in {"(", ")"}:
            classes.append("PAREN")
        else:
            classes.append("OTHER")
    return classes


def operator_family(expr: str) -> str:
    upper = expr.upper()
    if "BETWEEN" in upper:
        return "range"
    if "<>" in expr or "!=" in expr:
        return "inequality"
    if any(op in expr for op in ("<", ">")) and not any(op in expr for op in ("<=", ">=")):
        return "ordering"
    if any(op in expr for op in ("+", "-", "*", "/")):
        return "arithmetic_equality"
    if "=" in expr:
        return "equality"
    return "unknown"


def grammar_valid(expr: str) -> bool:
    if not expr or len(expr) > 160:
        return False
    if not ALLOWED_EXPR_RE.match(expr):
        return False
    if any(word in expr.lower() for word in BLOCKED_WORDS):
        return False
    return expr.count("(") == expr.count(")") and bool(TOKEN_RE.search(expr))


def length_bucket(expr: str) -> str:
    n = len(expr)
    return "short" if n <= 14 else "medium" if n <= 30 else "long"


def extract_grammar_features(expr: str, *, seed_id: str = "", family: str = "") -> dict[str, Any]:
    normalized = normalize_expr(expr)
    tokens = TOKEN_RE.findall(normalized)
    classes = token_classes(normalized)
    return {
        "seed_id": seed_id,
        "family": family,
        "expr_sha256": sha256_text(expr),
        "normalized_sha256": sha256_text(normalized),
        "normalized_len": len(normalized),
        "length_bucket": length_bucket(normalized),
        "token_count": len(tokens),
        "token_classes": classes,
        "token_class_signature": " ".join(classes),
        "operator_family": operator_family(normalized),
        "has_parentheses": "(" in normalized or ")" in normalized,
        "has_decimal": bool(re.search(r"\d+\.\d+", normalized)),
        "has_range_predicate": "BETWEEN" in normalized.upper(),
        "has_arithmetic": any(op in normalized for op in ("+", "-", "*", "/")),
        "grammar_valid": grammar_valid(normalized),
        "payload_redacted": True,
        "payload_exported": False,
    }


def compute_reward(candidate: Mapping[str, Any], observation: Mapping[str, Any], *, family_count: int, target_per_family: int, duplicate: bool) -> dict[str, Any]:
    reasons: list[str] = []
    reward = 0.0
    expected = str(candidate.get("expected_truth", "")).upper()
    checks = [
        (candidate.get("grammar_valid"), 1.0, "grammar_valid"),
        (observation.get("http_status") == 200, 1.0, "http_200"),
        (observation.get("waf_access_logged"), 1.0, "waf_access_logged"),
        (observation.get("waf_audit_logged"), 1.0, "waf_audit_logged"),
        (observation.get("backend_reached"), 2.0, "backend_reached"),
        (observation.get("observed_truth") == expected, 4.0, "oracle_matched"),
        (family_count < target_per_family, 1.0, "family_under_target"),
    ]
    for ok, value, label in checks:
        if ok:
            reward += value
            reasons.append(label)
    if duplicate:
        reward -= 5.0
        reasons.append("duplicate_penalty")
    accepted = reward >= 10.0 and not duplicate and all(label in reasons for label in ["grammar_valid", "http_200", "waf_access_logged", "waf_audit_logged", "backend_reached", "oracle_matched"])
    return {"accepted": accepted, "reward_total": round(reward, 3), "reward_reasons": reasons}


def public_candidate(candidate: Mapping[str, Any], observation: Mapping[str, Any], reward: Mapping[str, Any]) -> dict[str, Any]:
    payload = str(candidate.get("generated_payload", ""))
    return {
        "sample_id": candidate.get("sample_id"),
        "run_id": candidate.get("run_id"),
        "generator_kind": candidate.get("generator_kind"),
        "seed_id": candidate.get("seed_id"),
        "family": candidate.get("family"),
        "expected_truth": candidate.get("expected_truth"),
        "payload_sha256": sha256_text(payload),
        "normalized_sha256": sha256_text(normalize_expr(payload)),
        "payload_redacted": True,
        "payload_exported": False,
        "grammar_valid": bool(candidate.get("grammar_valid")),
        "token_class_signature": candidate.get("token_class_signature"),
        "operator_family": candidate.get("operator_family"),
        "length_bucket": candidate.get("length_bucket"),
        "http_status": observation.get("http_status"),
        "waf_access_logged": bool(observation.get("waf_access_logged")),
        "waf_audit_logged": bool(observation.get("waf_audit_logged")),
        "backend_reached": bool(observation.get("backend_reached")),
        "observed_truth": observation.get("observed_truth"),
        "oracle_matched": observation.get("observed_truth") == candidate.get("expected_truth"),
        "accepted": bool(reward.get("accepted")),
        "reward_total": reward.get("reward_total"),
        "reward_reasons": reward.get("reward_reasons"),
        "claim_scope": "controlled_lab_safe_boolean_oracle_only",
    }


@dataclass(frozen=True)
class SeedTemplate:
    seed_id: str
    family: str
    grammar_shape: str


def generate_expr_for_family(family: str, index: int, rng: random.Random) -> tuple[str, str]:
    base = rng.randint(20, 900) + index * 7
    truth = "TRUE" if index % 2 == 0 else "FALSE"
    if family == "numeric_equality":
        expr = f"{base} = {base if truth == 'TRUE' else base + 1}"
    elif family == "numeric_inequality":
        expr = f"{base} <> {base + 1 if truth == 'TRUE' else base}"
    elif family == "ordered_less_than":
        expr = f"{base} < {base + 1 if truth == 'TRUE' else base - 1}"
    elif family == "parenthesized_arithmetic":
        left = base % 100 + 10
        expr = f"({left} + {index + 1}) = {left + index + 1 if truth == 'TRUE' else left + index + 2}"
    elif family == "between_range":
        x = base % 400 + 50
        expr = f"{x} BETWEEN {x - 1 if truth == 'TRUE' else x + 1} AND {x + 1 if truth == 'TRUE' else x + 9}"
    else:
        expr = f"{base} = {base if truth == 'TRUE' else base + 1}"
    return expr, truth
