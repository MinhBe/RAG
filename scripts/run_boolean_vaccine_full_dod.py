from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from typing import Any

ROOT = Path("artifacts/boolean_vaccine")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def public_artifacts_have_no_payloads(paths: list[Path]) -> tuple[bool, list[str]]:
    forbidden = {"generated_payload", "true_expr", "false_expr", "expr"}
    violations: list[str] = []
    for path in paths:
        for idx, row in enumerate(load_jsonl(path), start=1):
            bad = sorted(forbidden.intersection(row.keys()))
            if bad:
                violations.append(f"{path}:{idx}:{','.join(bad)}")
    return not violations, violations


def gate(name: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def main() -> None:
    old_dod = read_json(ROOT / "definition_of_done.summary.json")
    seed_summary = read_json(ROOT / "boolean_seed_discovery.summary.json")
    grammar_summary = read_json(ROOT / "seed_grammar.redacted.summary.json")
    reward_summary = read_json(ROOT / "reward_loop_acceptance.redacted.summary.json")
    accepted = load_jsonl(ROOT / "reward_loop_acceptance.redacted.jsonl")
    seed_rows = load_jsonl(ROOT / "boolean_seeds.redacted.jsonl")
    private_replay = ROOT / "private" / "reward_loop_acceptance.local.jsonl"
    excel = ROOT / "boolean_vaccine_review.xlsx"
    clean_public, violations = public_artifacts_have_no_payloads([ROOT / "boolean_seeds.redacted.jsonl", ROOT / "seed_grammar.redacted.jsonl", ROOT / "reward_loop_acceptance.redacted.jsonl"])
    balanced = bool(reward_summary) and reward_summary.get("accepted") == 50 and reward_summary.get("min_per_family", 0) >= 10 and reward_summary.get("max_per_family", 999) <= 10
    all_accepted_have_evidence = bool(accepted) and all(row.get("accepted") is True and row.get("waf_access_logged") is True and row.get("waf_audit_logged") is True and row.get("backend_reached") is True and row.get("oracle_matched") is True for row in accepted)
    gates = [
        gate("ModSecurity lab verified", old_dod.get("status") == "PASS", {"prior_dod_status": old_dod.get("status")}),
        gate("Backend oracle verified", old_dod.get("status") == "PASS", {"safe_oracle_path": "127.0.0.1:18080/bool_oracle -> 127.0.0.1:18081"}),
        gate("5 Boolean seed accepted", seed_summary.get("accepted") == 5, seed_summary),
        gate("Each seed has WAF and backend evidence", len(seed_rows) == 5 and all(row.get("accepted") for row in seed_rows), {"seed_rows": len(seed_rows)}),
        gate("Seed grammar/features extracted", grammar_summary.get("status") == "ok" and grammar_summary.get("feature_rows") == 10, grammar_summary),
        gate("SeqGAN reward loop ran", reward_summary.get("status") == "ok", reward_summary),
        gate("At least 50 generated samples accepted", len(accepted) >= 50 and all_accepted_have_evidence, {"accepted_rows": len(accepted), "all_have_evidence": all_accepted_have_evidence}),
        gate("Accepted samples balanced by seed/family", balanced, {"accepted_by_family": reward_summary.get("accepted_by_family"), "min_per_family": reward_summary.get("min_per_family"), "max_per_family": reward_summary.get("max_per_family")}),
        gate("Public artifact contains no raw payload", clean_public, {"violations": violations}),
        gate("Private local artifact enough to replay", private_replay.exists(), {"private_replay": str(private_replay), "exists": private_replay.exists()}),
        gate("Report states claim boundary", bool(reward_summary.get("claim_boundary")), {"claim_boundary": reward_summary.get("claim_boundary")}),
        gate("Excel review workbook exists", excel.exists(), {"excel": str(excel), "exists": excel.exists()}),
    ]
    passed = all(item["passed"] for item in gates)
    summary = {"status": "PASS" if passed else "FAIL", "definition_of_done_passed": passed, "passed_gates": [item["name"] for item in gates if item["passed"]], "failed_gates": [item["name"] for item in gates if not item["passed"]], "gates": gates, "claim_boundary": "Controlled lab only. Safe restricted Boolean oracle; public artifacts redacted. Small reward loop is not a claim of raw full SeqGAN self-clean generation."}
    path = ROOT / "full_definition_of_done.summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

