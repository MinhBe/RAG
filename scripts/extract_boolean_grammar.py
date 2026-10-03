from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from typing import Any

from app.core.boolean_vaccine import extract_grammar_features

DEFAULT_PRIVATE_SEEDS = Path("artifacts/boolean_vaccine/private/boolean_seeds.local.jsonl")
DEFAULT_PUBLIC_OUTPUT = Path("artifacts/boolean_vaccine/seed_grammar.redacted.jsonl")
DEFAULT_PRIVATE_OUTPUT = Path("artifacts/boolean_vaccine/private/seed_grammar.local.jsonl")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract redacted grammar/features from accepted Boolean seeds.")
    parser.add_argument("--private-seeds", type=Path, default=DEFAULT_PRIVATE_SEEDS)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--private-output", type=Path, default=DEFAULT_PRIVATE_OUTPUT)
    args = parser.parse_args()
    seeds = load_jsonl(args.private_seeds)
    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for seed in seeds:
        seed_id = str(seed["seed_id"])
        family = str(seed["family"])
        for label, expr_key in (("TRUE", "true_expr"), ("FALSE", "false_expr")):
            expr = str(seed[expr_key])
            features = extract_grammar_features(expr, seed_id=seed_id, family=family)
            features.update({
                "truth_label": label,
                "grammar_shape": seed.get("grammar_shape"),
                "source": "accepted_boolean_seed",
            })
            public_rows.append(features)
            private_row = dict(features)
            private_row["expr"] = expr
            private_rows.append(private_row)
    write_jsonl(args.public_output, public_rows)
    write_jsonl(args.private_output, private_rows)
    summary = {
        "status": "ok" if public_rows and all(row["grammar_valid"] for row in public_rows) else "partial",
        "seed_count": len(seeds),
        "feature_rows": len(public_rows),
        "families": sorted({str(row["family"]) for row in public_rows}),
        "payloads_redacted_in_public": True,
        "public_output": str(args.public_output),
        "private_output": str(args.private_output),
    }
    args.public_output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

