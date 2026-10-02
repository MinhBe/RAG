# ruff: noqa
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Mapping

PREFIX_RE = re.compile(r"^(?P<prefix>(?:<[^>]+>)+)\s*(?P<payload>.*)$", re.S)
TAG_RE = re.compile(r"<(?P<k>[A-Za-z_]+)=(?P<v>[^>]+)>")
WORD_RE = re.compile(r"[A-Za-z_]+|<>|!=|>=|<=|\?\||\?&|&&|@>|<@|!~\*|~\*|!~|~|=|>|<|\(|\)|\[|\]|,|\+|-|\*|/|%")
STRING_RE = re.compile(r"'(?:''|[^'])*'")
DANGEROUS_RE = re.compile(r"(;|--|\b(SELECT|UNION|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|GRANT|REVOKE|TRUNCATE|pg_sleep|dblink|lo_import|pg_read_file|SLEEP|BENCHMARK)\b)", re.I)
BOOL_TOKENS = {
    "=", "<>", "!=", ">", "<", ">=", "<=", "IS", "NULL", "TRUE", "FALSE", "IN",
    "ANY", "ALL", "LIKE", "ILIKE", "SIMILAR", "TO", "BETWEEN", "AND", "OR", "NOT",
    "DISTINCT", "FROM", "?", "&&", "@>", "<@", "~", "!~", "~*", "!~*",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def parse_condition_prefix(text: str) -> tuple[dict[str, str], str]:
    m = PREFIX_RE.match(str(text or ""))
    if not m:
        return {}, str(text or "")
    tags = {mm.group("k").upper(): mm.group("v") for mm in TAG_RE.finditer(m.group("prefix"))}
    return tags, m.group("payload").strip()


def tokens(sql: str) -> list[str]:
    no_str = STRING_RE.sub("'<STR>'", str(sql or ""))
    return [x.upper() for x in WORD_RE.findall(no_str)]


def split_contract_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return []
        try:
            parsed = json.loads(s)
            raw = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            raw = re.split(r"\s*\|\s*|\s*,\s*", s)
    return [str(x).strip().upper() for x in raw if str(x).strip()]


def balanced_quotes(sql: str) -> bool:
    quote = False
    i = 0
    while i < len(sql):
        if sql[i] == "'":
            if quote and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            quote = not quote
        i += 1
    return not quote


def balanced_pairs(sql: str) -> bool:
    stack = []
    pairs = {')': '(', ']': '['}
    quote = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            if quote and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            quote = not quote
        elif not quote:
            if ch in "([":
                stack.append(ch)
            elif ch in ")]":
                if not stack or stack[-1] != pairs[ch]:
                    return False
                stack.pop()
        i += 1
    return not quote and not stack


def required_token_score(payload: str, required_tokens: Any) -> float:
    req = split_contract_tokens(required_tokens)
    if not req:
        return 1.0
    tok = set(tokens(payload))
    upper = payload.upper()
    hits = sum(1 for r in req if r in tok or r in upper)
    return hits / max(len(req), 1)


def forbidden_token_valid(payload: str, forbidden_tokens: Any) -> bool:
    forbidden = split_contract_tokens(forbidden_tokens)
    if not forbidden:
        return DANGEROUS_RE.search(payload) is None
    upper = payload.upper()
    tok = set(tokens(payload))
    if DANGEROUS_RE.search(payload):
        return False
    return not any(f in tok or f in upper for f in forbidden)


def bool_signal(payload: str) -> bool:
    tok = set(tokens(payload))
    return bool(tok & BOOL_TOKENS)


def slot_sanity(payload: str, contract: Mapping[str, Any]) -> bool:
    schema = contract.get("slot_schema") or {}
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except Exception:
            schema = {}
    slots = schema.get("slots", []) if isinstance(schema, dict) else []
    if not slots:
        return True
    p = str(payload)
    up = p.upper()
    ok_count = 0
    checked = 0
    for slot in slots:
        if not isinstance(slot, Mapping):
            continue
        st = str(slot.get("type", "")).lower()
        allowed = slot.get("allowed_values")
        checked += 1
        ok = True
        if allowed:
            ok = any(str(v).upper() in up for v in allowed)
        elif "integer" in st or st in {"int", "int_literal"}:
            ok = re.search(r"\b\d+\b", p) is not None
        elif "string" in st or "text" in st:
            ok = STRING_RE.search(p) is not None
        elif "operator" in st:
            ok = bool(set(tokens(p)) & {"=", "<>", "!=", ">", "<", ">=", "<=", "IN", "LIKE", "ILIKE", "BETWEEN", "?", "&&", "@>", "<@", "~", "!~"})
        elif "array" in st:
            ok = "ARRAY[" in up or ("[" in p and "]" in p)
        elif "json" in st:
            ok = "JSON" in up or "{" in p or "[" in p
        elif "inet" in st or "cidr" in st:
            ok = "INET" in up or "CIDR" in up or re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", p) is not None
        elif "uuid" in st:
            ok = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}", p) is not None
        ok_count += int(bool(ok))
    return checked == 0 or (ok_count / checked) >= 0.70


@dataclass
class StaticValidation:
    payload: str
    static_score: float
    contract_valid: bool
    delimiter_valid: bool
    quote_valid: bool
    parenthesis_valid: bool
    boolean_signal_valid: bool
    required_tokens_valid: bool
    forbidden_tokens_valid: bool
    slot_sanity_valid: bool
    error_class: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def static_validate(payload: str, contract: Mapping[str, Any] | None = None) -> StaticValidation:
    contract = contract or {}
    payload = str(payload or "")
    q_ok = balanced_quotes(payload)
    p_ok = balanced_pairs(payload)
    b_ok = bool_signal(payload)
    req_score = required_token_score(payload, contract.get("required_tokens", ""))
    req_ok = req_score >= 0.999
    forbid_ok = forbidden_token_valid(payload, contract.get("forbidden_tokens", ""))
    slot_ok = slot_sanity(payload, contract)
    delimiter_ok = p_ok and q_ok
    weights = {
        "delimiter": 0.18,
        "quote": 0.12,
        "parenthesis": 0.12,
        "boolean": 0.16,
        "required": 0.18,
        "forbidden": 0.12,
        "slot": 0.12,
    }
    score = (
        weights["delimiter"] * float(delimiter_ok)
        + weights["quote"] * float(q_ok)
        + weights["parenthesis"] * float(p_ok)
        + weights["boolean"] * float(b_ok)
        + weights["required"] * req_score
        + weights["forbidden"] * float(forbid_ok)
        + weights["slot"] * float(slot_ok)
    )
    fails = []
    for name, ok in [("delimiter", delimiter_ok), ("quote", q_ok), ("parenthesis", p_ok), ("boolean", b_ok), ("required_tokens", req_ok), ("forbidden_tokens", forbid_ok), ("slot_sanity", slot_ok)]:
        if not ok:
            fails.append(name)
    contract_valid = delimiter_ok and q_ok and p_ok and b_ok and req_ok and forbid_ok and slot_ok
    return StaticValidation(
        payload=payload,
        static_score=round(float(score), 6),
        contract_valid=contract_valid,
        delimiter_valid=delimiter_ok,
        quote_valid=q_ok,
        parenthesis_valid=p_ok,
        boolean_signal_valid=b_ok,
        required_tokens_valid=req_ok,
        forbidden_tokens_valid=forbid_ok,
        slot_sanity_valid=slot_ok,
        error_class="ok" if not fails else "+".join(fails),
    )


def repair_small(payload: str, contract: Mapping[str, Any] | None = None) -> tuple[str, list[str]]:
    """Small deterministic repair for generated candidates.

    This does not invent exploit context. It only repairs obvious local syntax issues:
    quote closure and unmatched closing/opening delimiters.
    """
    p = str(payload or "")
    actions: list[str] = []
    # Remove excess right parentheses/brackets from left to right.
    out = []
    stack = []
    quote = False
    i = 0
    while i < len(p):
        ch = p[i]
        if ch == "'":
            if quote and i + 1 < len(p) and p[i + 1] == "'":
                out.extend([ch, p[i + 1]])
                i += 2
                continue
            quote = not quote
            out.append(ch)
        elif not quote and ch in "([":
            stack.append(ch)
            out.append(ch)
        elif not quote and ch in ")]":
            want = "(" if ch == ")" else "["
            if stack and stack[-1] == want:
                stack.pop()
                out.append(ch)
            else:
                actions.append(f"drop_unmatched_{ch}")
        else:
            out.append(ch)
        i += 1
    p2 = "".join(out)
    if quote:
        p2 += "'"
        actions.append("close_quote")
    while stack:
        op = stack.pop()
        closer = ")" if op == "(" else "]"
        p2 += closer
        actions.append(f"close_{op}")
    return p2, actions
