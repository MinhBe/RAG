# ruff: noqa
from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from typing import Any

SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE",
    "TRUE", "FALSE", "NULL", "UNKNOWN",
    "AND", "OR", "NOT", "IS", "IN", "LIKE", "ILIKE", "BETWEEN",
    "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END",
    "AS", "CAST", "COALESCE", "NULLIF",
    "EXISTS", "ALL", "ANY", "SOME",
    "SIMILAR", "TO", "ESCAPE",
    "ROW", "FOR", "ARRAY", "JSON", "JSONB", "INET", "CIDR", "UUID",
}
ALLOWED_FUNCTIONS = {
    "LENGTH", "CHAR_LENGTH", "CHARACTER_LENGTH",
    "SUBSTRING", "LOWER", "UPPER",
    "COALESCE", "NULLIF", "ABS",
}
CORRUPTION_TARGETS = {
    "TRUE", "FALSE", "NULL", "AND", "OR", "NOT", "IS",
    "WHEN", "THEN", "ELSE", "END", "BETWEEN", "LIKE", "ILIKE", "IN",
    "DISTINCT", "FROM", "LENGTH", "SUBSTRING", "COALESCE", "NULLIF",
}

TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z_0-9]*|<>|!=|>=|<=|\?\||\?&|&&|@>|<@|!~\*|~\*|!~|~|=|>|<|\(|\)|\[|\]|,|\+|-|\*|/|%|\d+(?:\.\d+)?|'(?:''|[^'])*'",
    re.I,
)


@dataclass(frozen=True)
class ParserLikeAudit:
    clean: bool
    score: float
    reasons: tuple[str, ...]
    unknown_alpha_rate: float
    mixed_numeric_alpha: tuple[str, ...]
    repair_action_count: int
    version: str = "parserlike_v4"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["reasons"] = ";".join(self.reasons)
        d["mixed_numeric_alpha"] = ";".join(self.mixed_numeric_alpha)
        return d


def safe_text(x: Any) -> str:
    if x is None:
        return ""
    try:
        # pandas/numpy NaN is not equal to itself.
        if x != x:
            return ""
    except Exception:
        pass
    return str(x)


def strip_sql_strings(s: Any) -> tuple[str, bool]:
    s = safe_text(s)
    out: list[str] = []
    i = 0
    in_str = False
    while i < len(s):
        ch = s[i]
        if ch == "'":
            out.append(" ")
            if in_str:
                if i + 1 < len(s) and s[i + 1] == "'":
                    out.append(" ")
                    i += 2
                    continue
                in_str = False
            else:
                in_str = True
            i += 1
            continue
        out.append(" " if in_str else ch)
        i += 1
    return "".join(out), in_str


def balanced_parenthesis_outside_strings(s: Any) -> bool:
    clean, _ = strip_sql_strings(s)
    depth = 0
    for ch in clean:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def balanced_quote(s: Any) -> bool:
    _, in_str = strip_sql_strings(s)
    return not in_str


def alpha_tokens_outside_strings(s: Any) -> list[str]:
    clean, _ = strip_sql_strings(s)
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*", clean)


def lexical_alpha_core(tok: str) -> str:
    return re.sub(r"\d+$", "", tok.upper())


def tokenize_outside_strings(s: Any) -> list[str]:
    clean, _ = strip_sql_strings(s)
    return [t.upper() for t in TOKEN_RE.findall(clean)]


def mixed_numeric_alpha_tokens(s: Any) -> list[str]:
    clean, _ = strip_sql_strings(s)
    toks = re.findall(r"\b[A-Za-z0-9_]+\b", clean)
    bad: list[str] = []
    for t in toks:
        if re.search(r"[A-Za-z_]", t) and re.search(r"\d", t):
            if re.match(r"^[A-Za-z_]\d{1,3}$", t):
                continue
            if re.match(r"^\d+[A-Za-z_]+", t):
                bad.append(t)
            elif re.match(r"^[A-Za-z_]+\d+[A-Za-z_]+", t):
                bad.append(t)
    return bad


def is_keyword_corruption(tok: str) -> bool:
    t = lexical_alpha_core(tok)
    if not t or t in SQL_KEYWORDS or t in ALLOWED_FUNCTIONS:
        return False
    if len(t) == 1:
        return False
    for kw in CORRUPTION_TARGETS:
        if kw in t and t != kw and len(t) <= len(kw) + 6:
            return True
    for kw in CORRUPTION_TARGETS:
        ratio = difflib.SequenceMatcher(None, t, kw).ratio()
        if ratio >= 0.80 and abs(len(t) - len(kw)) <= 3:
            return True
    return False


def has_keyword_corruption(s: Any) -> bool:
    return any(is_keyword_corruption(tok) for tok in alpha_tokens_outside_strings(s))


def unknown_alpha_rate(s: Any) -> float:
    toks = alpha_tokens_outside_strings(s)
    if not toks:
        return 0.0
    bad = 0
    for tok in toks:
        t = lexical_alpha_core(tok)
        if not t:
            continue
        if t in SQL_KEYWORDS or t in ALLOWED_FUNCTIONS:
            continue
        if len(t) == 1:
            continue
        if re.match(r"^[A-Z]\d{1,3}$", t):
            continue
        bad += 1
    return bad / max(1, len(toks))


def invalid_is_context(s: Any) -> bool:
    toks = tokenize_outside_strings(s)
    for i, tok in enumerate(toks):
        if tok != "IS":
            continue
        if i + 1 >= len(toks):
            return True
        nxt = lexical_alpha_core(toks[i + 1])
        if nxt == "NOT":
            if i + 2 >= len(toks):
                return True
            nxt2 = lexical_alpha_core(toks[i + 2])
            if nxt2 not in {"TRUE", "FALSE", "NULL", "DISTINCT", "UNKNOWN"}:
                return True
        else:
            if nxt not in {"TRUE", "FALSE", "NULL", "DISTINCT", "UNKNOWN"}:
                return True
    return False


def function_typo(s: Any) -> bool:
    clean, _ = strip_sql_strings(s)
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\(", clean):
        fn = lexical_alpha_core(m.group(1))
        if not fn:
            continue
        if fn in ALLOWED_FUNCTIONS or fn in SQL_KEYWORDS:
            continue
        if len(fn) > 1:
            return True
    return False


def required_order_bad(s: Any) -> bool:
    clean, _ = strip_sql_strings(s)
    u = clean.upper()
    bad_patterns = [
        r"\bTRUE\s+FALSE\b",
        r"\bFALSE\s+TRUE\b",
        r"\bTHEN\s+THEN\b",
        r"\bELSE\s+ELSE\b",
        r"\bEND\s+END\s+END\b",
        r"\bIS\s+TRUE\s+FALSE\b",
        r"\bIS\s+FALSE\s+TRUE\b",
        r"\bAND\s+(TRUE|FALSE)\s*$",
        r"\bOR\s+(TRUE|FALSE)\s*$",
    ]
    return any(re.search(p, u) for p in bad_patterns)



def _prev_word_before(clean: str, idx: int) -> str:
    j = idx - 1
    while j >= 0 and clean[j].isspace():
        j -= 1
    k = j
    while k >= 0 and (clean[k].isalnum() or clean[k] == "_"):
        k -= 1
    return clean[k + 1:j + 1].upper()


def tuple_or_top_level_comma_boolean_context(s: Any) -> bool:
    """Detect row-expression commas that v4 often accepted as boolean predicates.

    PostgreSQL accepts function-argument commas such as COALESCE(a, FALSE) and
    array commas such as ARRAY[1, 2].  But a generated candidate like
    NOT ((predicate), FALSE) produces a row value inside a boolean context; it is
    a high-risk static false positive for the corpus goal.
    """
    clean, _ = strip_sql_strings(s)
    allowed_arg_contexts = {
        "COALESCE", "NULLIF", "LOWER", "UPPER", "SUBSTRING", "POSITION",
        "LENGTH", "CHAR_LENGTH", "CHARACTER_LENGTH", "ABS", "GREATEST",
        "LEAST", "REGEXP_MATCHES", "ARRAY",
    }
    stack: list[tuple[str, str]] = []
    for i, ch in enumerate(clean):
        if ch == "(":
            prev = _prev_word_before(clean, i)
            ctx = "func" if prev in allowed_arg_contexts else "paren"
            stack.append(("(", ctx))
        elif ch == "[":
            stack.append(("[", "array"))
        elif ch == "{":
            stack.append(("{", "brace"))
        elif ch in ")]}":
            if stack:
                stack.pop()
        elif ch == ",":
            if not stack:
                return True
            if stack[-1][1] == "paren":
                return True
    return False


def no_boolean_signal(s: Any) -> bool:
    clean, _ = strip_sql_strings(s)
    return not bool(re.search(
        r"(=|<>|!=|>=|<=|>|<|\bLIKE\b|\bILIKE\b|\bBETWEEN\b|\bIS\b|\bIN\b|\bNOT\b|\bAND\b|\bOR\b|&&|@>|<@|~|!~|\bCASE\b|\bCOALESCE\b|\bNULLIF\b)",
        clean,
        re.I,
    ))


def strict_shape_reasons(s: Any) -> list[str]:
    clean, _ = strip_sql_strings(s)
    u = clean.upper()
    toks = tokenize_outside_strings(clean)
    joined = " ".join(toks)
    reasons: list[str] = []

    if re.search(r"\bFROM\b", u) and not re.search(r"\bIS\s+(?:NOT\s+)?DISTINCT\s+FROM\b", u):
        reasons.append("from_without_is_distinct")

    if re.search(r"\(\s*\)", clean):
        reasons.append("empty_parentheses")

    if re.search(r"\b(CASE|WHEN|THEN|ELSE|END)\b", u):
        has_case = "CASE" in toks
        has_when = "WHEN" in toks
        has_then = "THEN" in toks
        has_end = "END" in toks
        if not (has_case and has_when and has_then and has_end):
            reasons.append("case_fragment_without_case")
        if toks.count("ELSE") > 1:
            reasons.append("case_multiple_else")

    if re.search(r"\bBETWEEN\b", u) and not re.search(r"\bBETWEEN\b.+\bAND\b", u):
        reasons.append("between_missing_and")

    if re.search(r"\bIN\s*(?!\()", u):
        reasons.append("in_rhs_not_parenthesized")

    # Bare comparison at terminal or followed by another operator/lone keyword.
    if re.search(r"(=|<>|!=|>=|<=|>|<)\s*(?:\)|\]|\s)*$", clean):
        reasons.append("predicate_bad_rhs")
    if re.search(r"(=|<>|!=|>=|<=|>|<)\s+(?:AND|OR|WHEN|THEN|ELSE|END|BETWEEN|IN|LIKE|ILIKE)\b", u):
        reasons.append("predicate_bad_rhs")

    if re.search(r"\bNOT\s*(?:\)|$)", u):
        reasons.append("not_bad_rhs")

    if toks and toks[-1] in {"AND", "OR", "NOT", "IS", "IN", "LIKE", "ILIKE", "BETWEEN", "THEN", "ELSE", "WHEN"}:
        reasons.append("bad_terminal_token")

    # Function arity checks for functions the corpus commonly uses.
    if re.search(r"\b[A-Z_][A-Z_0-9]*\s*\(\s*\)", u):
        reasons.append("empty_function_call")
    for m in re.finditer(r"\bNULLIF\s*\(([^()]*)\)", clean, re.I):
        if len([x for x in m.group(1).split(",") if x.strip()]) != 2:
            reasons.append("nullif_arity_bad")
    for m in re.finditer(r"\bCOALESCE\s*\(([^()]*)\)", clean, re.I):
        if len([x for x in m.group(1).split(",") if x.strip()]) < 2:
            reasons.append("coalesce_predicate_arg_without_fallback")

    # Repeated literal tokens usually mean the generator concatenated fragments.
    if re.search(r"(?:'[^']*'|\b\d+\b)\s+(?:'[^']*'|\b\d+\b)", clean):
        reasons.append("consecutive_literal_tokens")

    if re.search(r"'(?:''|[^'])*'\s+[A-Za-z_][A-Za-z_0-9]*", clean):
        reasons.append("literal_followed_by_unknown_identifier")

    # Corrupted comparison operator sequences.
    if re.search(r"(?:={2,}|<>{2,}|!!=|>>=|<<=|=<>|<=>|><)", clean):
        reasons.append("comparison_operator_corruption")

    if re.search(r"(=|<>|!=|>=|<=|>|<)\s+[A-Za-z]\s*(?:$|\)|AND|OR)", clean, re.I):
        reasons.append("single_letter_rhs_identifier")

    if tuple_or_top_level_comma_boolean_context(s):
        reasons.append("tuple_or_top_level_comma_boolean_context")
    if re.search(r"(=|<>|!=|>=|<=|>|<|LIKE|ILIKE|~|!~|&&|@>)\s*$", clean.strip(), re.I):
        reasons.append("bad_terminal_operator")
    if no_boolean_signal(s):
        reasons.append("no_boolean_signal")

    # De-duplicate while preserving order.
    return list(dict.fromkeys(reasons))


def parserlike_static_audit(
    payload: Any,
    *,
    repair_count: int = 0,
    unknown_alpha_max: float = 0.12,
    max_repair_actions: int = 1,
    version: str = "v4",
) -> ParserLikeAudit:
    p = safe_text(payload)
    reasons: list[str] = []

    if not balanced_quote(p):
        reasons.append("unbalanced_quote")
    if not balanced_parenthesis_outside_strings(p):
        reasons.append("unbalanced_parenthesis")
    if has_keyword_corruption(p):
        reasons.append("keyword_corruption")
    if invalid_is_context(p):
        reasons.append("invalid_is_context")
    if function_typo(p):
        reasons.append("function_typo")
    if required_order_bad(p):
        reasons.append("required_order_bad")

    mixed = mixed_numeric_alpha_tokens(p)
    if mixed:
        reasons.append("mixed_numeric_alpha")

    uar = unknown_alpha_rate(p)
    if uar > unknown_alpha_max:
        reasons.append("unknown_alpha_rate_gt_threshold")

    if repair_count > max_repair_actions:
        reasons.append("repair_action_count_gt_budget")

    if str(version).lower() in {"v2", "v3", "v4", "v5", "strict"}:
        reasons.extend(strict_shape_reasons(p))

    # Score is a compact, monotone audit signal rather than a runtime claim.
    weights = {
        "unbalanced_quote": 0.18,
        "unbalanced_parenthesis": 0.18,
        "keyword_corruption": 0.14,
        "invalid_is_context": 0.10,
        "function_typo": 0.10,
        "required_order_bad": 0.08,
        "mixed_numeric_alpha": 0.08,
        "unknown_alpha_rate_gt_threshold": 0.08,
        "repair_action_count_gt_budget": 0.10,
        "predicate_bad_rhs": 0.18,
        "bad_terminal_token": 0.14,
        "case_fragment_without_case": 0.14,
        "empty_function_call": 0.12,
        "from_without_is_distinct": 0.10,
        "empty_parentheses": 0.10,
        "between_missing_and": 0.10,
        "in_rhs_not_parenthesized": 0.10,
        "not_bad_rhs": 0.10,
        "nullif_arity_bad": 0.10,
        "coalesce_predicate_arg_without_fallback": 0.10,
        "case_multiple_else": 0.10,
        "consecutive_literal_tokens": 0.08,
        "literal_followed_by_unknown_identifier": 0.08,
        "comparison_operator_corruption": 0.12,
        "single_letter_rhs_identifier": 0.08,
        "tuple_or_top_level_comma_boolean_context": 0.14,
        "bad_terminal_operator": 0.14,
        "no_boolean_signal": 0.18,
    }
    penalty = sum(weights.get(r, 0.08) for r in dict.fromkeys(reasons))
    score = max(0.0, min(1.0, 1.0 - penalty))
    reasons = list(dict.fromkeys(reasons))
    return ParserLikeAudit(
        clean=(len(reasons) == 0),
        score=round(float(score), 6),
        reasons=tuple(reasons),
        unknown_alpha_rate=round(float(uar), 6),
        mixed_numeric_alpha=tuple(mixed),
        repair_action_count=int(repair_count),
        version=f"parserlike_{version}",
    )
