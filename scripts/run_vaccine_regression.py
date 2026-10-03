from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.vaccine_regression import run_vaccine_regression

DEFAULT_DATASET = REPO_ROOT / "artifacts/demo_b/seqgan_vaccine_cases.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts/vaccine_regression/summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the redacted Hermes vaccine regression benchmark."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    summary = run_vaccine_regression(
        dataset_path=args.dataset,
        output_path=args.output,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
