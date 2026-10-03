from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

S234 = Path("artifacts/vaccine_sprints_2_3_4/sprints_2_3_4_definition_of_done.summary.json")
S567 = Path("artifacts/vaccine_sprints_5_6_7")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gate(name: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes vaccine regression gate for controlled lab artifacts.")
    parser.add_argument("--root", type=Path, default=S567)
    parser.add_argument("--attack-flag-threshold", type=float, default=0.90)
    parser.add_argument("--benign-allow-threshold", type=float, default=0.95)
    parser.add_argument("--max-fpr", type=float, default=0.05)
    parser.add_argument("--max-fnr", type=float, default=0.10)
    args = parser.parse_args()
    s234 = read_json(S234)
    s5 = read_json(args.root / "sprint5_seqgan_adapter.summary.json")
    s7 = read_json(args.root / "sprint7_ml_baseline.summary.json")
    sprint4_metrics = s234.get("sprint4_metrics", {})
    gates = [
        gate("sprint_2_4_prereq_pass", s234.get("status") == "PASS", {"status": s234.get("status")}),
        gate("seqgan_adapter_reward_loop_present", s5.get("status") == "PASS" and s5.get("reward_stage_called", 0) >= 50, s5),
        gate("not_projection_only", s5.get("projected_generated") == 0 and s5.get("raw_generated", 0) >= 50, {"raw_generated": s5.get("raw_generated"), "projected_generated": s5.get("projected_generated")}),
        gate("attack_flag_rate_threshold", sprint4_metrics.get("attack_flag_rate", 0.0) >= args.attack_flag_threshold, {"value": sprint4_metrics.get("attack_flag_rate"), "threshold": args.attack_flag_threshold}),
        gate("benign_allow_rate_threshold", sprint4_metrics.get("benign_allow_rate", 0.0) >= args.benign_allow_threshold, {"value": sprint4_metrics.get("benign_allow_rate"), "threshold": args.benign_allow_threshold}),
        gate("fpr_threshold", sprint4_metrics.get("false_positive_rate", 1.0) <= args.max_fpr, {"value": sprint4_metrics.get("false_positive_rate"), "threshold": args.max_fpr}),
        gate("fnr_threshold", sprint4_metrics.get("false_negative_rate", 1.0) <= args.max_fnr, {"value": sprint4_metrics.get("false_negative_rate"), "threshold": args.max_fnr}),
        gate("ml_baseline_ready", s7.get("status") == "PASS", {"status": s7.get("status"), "models": s7.get("models")}),
    ]
    passed = all(row["passed"] for row in gates)
    summary = {
        "status": "PASS" if passed else "FAIL",
        "definition_of_done_passed": passed,
        "gates": gates,
        "passed_gates": [g["name"] for g in gates if g["passed"]],
        "failed_gates": [g["name"] for g in gates if not g["passed"]],
        "one_command": "uv run python scripts/run_vaccine_gate.py",
        "claim_boundary": "Controlled lab artifact regression gate; not a production WAF deployment claim.",
    }
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / "sprint6_vaccine_gate.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
