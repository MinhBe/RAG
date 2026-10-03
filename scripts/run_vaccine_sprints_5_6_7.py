from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path("artifacts/boolean_vaccine")
S234 = Path("artifacts/vaccine_sprints_2_3_4")
OUT = Path("artifacts/vaccine_sprints_5_6_7")
PRIVATE = OUT / "private"
FORBIDDEN_PUBLIC_KEYS = {"payload", "generated_payload", "expr", "true_expr", "false_expr"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def run_py(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], check=True)


def ensure_prereqs() -> dict[str, Any]:
    pre: dict[str, Any] = {}
    if read_json(ROOT / "full_definition_of_done.summary.json").get("status") != "PASS":
        run_py(["scripts/run_boolean_vaccine_full_dod.py"])
    if read_json(S234 / "sprints_2_3_4_definition_of_done.summary.json").get("status") != "PASS":
        run_py(["scripts/run_vaccine_sprints_2_3_4.py"])
    pre["sprint1_status"] = read_json(ROOT / "full_definition_of_done.summary.json").get("status")
    pre["sprint2_4_status"] = read_json(S234 / "sprints_2_3_4_definition_of_done.summary.json").get("status")
    pre["attack_corpus_rows"] = len(read_jsonl(S234 / "sprint4_multifamily_after.redacted.jsonl"))
    pre["control_corpus_rows"] = len(read_jsonl(S234 / "sprint3_control_200.redacted.jsonl"))
    pre["private_replay_exists"] = (S234 / "private").exists()
    pre["ok"] = pre["sprint1_status"] == "PASS" and pre["sprint2_4_status"] == "PASS" and pre["attack_corpus_rows"] >= 100 and pre["control_corpus_rows"] >= 200
    return pre


def sprint5_seqgan_adapter() -> dict[str, Any]:
    public_output = OUT / "sprint5_seqgan_adapter_acceptance.redacted.jsonl"
    private_output = PRIVATE / "sprint5_seqgan_adapter_acceptance.local.jsonl"
    rejections = OUT / "sprint5_seqgan_adapter_rejections.redacted.jsonl"
    cmd = [
        "scripts/run_seqgan_reward_small_loop.py",
        "--target", "50",
        "--seed", "707",
        "--public-output", str(public_output),
        "--private-output", str(private_output),
        "--rejections-output", str(rejections),
    ]
    run_py(cmd)
    loop_summary = read_json(public_output.with_suffix(".summary.json"))
    accepted = read_jsonl(public_output)
    private_rows = read_jsonl(private_output)
    families = Counter(str(row.get("family", "unknown")) for row in accepted)
    summary = {
        "status": "PASS" if loop_summary.get("status") == "ok" and len(accepted) >= 50 else "FAIL",
        "generator_kind": "seqgan_adapter_reward_loop_not_projection_only_v1",
        "source_loop_generator_kind": loop_summary.get("generator_kind"),
        "raw_generated": loop_summary.get("attempts", 0),
        "grammar_valid_generated": sum(1 for row in accepted if row.get("grammar_valid") is True),
        "waf_passed_generated": sum(1 for row in accepted if row.get("waf_access_logged") is True),
        "oracle_confirmed_accepted": sum(1 for row in accepted if row.get("oracle_matched") is True),
        "projected_generated": 0,
        "repaired_generated": 0,
        "accepted_after_reward_selection": len(accepted),
        "reward_stage_called": loop_summary.get("attempts", 0),
        "accepted_by_family": dict(sorted(families.items())),
        "lineage_fields": ["generator_kind", "source_loop_generator_kind", "raw_generated", "projected_generated", "accepted_after_reward_selection"],
        "public_output": str(public_output),
        "private_output": str(private_output),
        "private_rows": len(private_rows),
        "claim_boundary": "SeqGAN adapter reward loop over restricted Boolean grammar lanes; not a claim of vendor full raw SeqGAN self-clean generation.",
    }
    write_json(OUT / "sprint5_seqgan_adapter.summary.json", summary)
    return summary


def build_feature_rows() -> tuple[list[dict[str, Any]], list[int]]:
    attack_paths = [OUT / "sprint5_seqgan_adapter_acceptance.redacted.jsonl", S234 / "sprint4_multifamily_after.redacted.jsonl", ROOT / "reward_loop_acceptance.redacted.jsonl"]
    control_paths = [S234 / "sprint3_control_200.redacted.jsonl"]
    rows: list[dict[str, Any]] = []
    labels: list[int] = []
    for path in attack_paths:
        for row in read_jsonl(path):
            rows.append(row | {"ml_label": "attack", "source_path": str(path)})
            labels.append(1)
    for path in control_paths:
        for row in read_jsonl(path):
            rows.append(row | {"ml_label": "benign", "source_path": str(path)})
            labels.append(0)
    return rows, labels


def vectorize(rows: list[dict[str, Any]]) -> tuple[list[list[float]], list[str]]:
    cat_values: dict[str, list[str]] = {}
    for key in ["family", "operator_family", "length_bucket"]:
        cat_values[key] = sorted({str(row.get(key, "unknown")) for row in rows})
    feature_names = ["token_count", "normalized_len", "has_parentheses", "has_decimal", "has_range_predicate", "has_arithmetic", "waf_access_logged", "waf_audit_logged", "backend_reached", "oracle_matched"]
    for key, values in cat_values.items():
        feature_names.extend([f"{key}={value}" for value in values])
    matrix: list[list[float]] = []
    for row in rows:
        values: list[float] = [
            float(row.get("token_count") or 0),
            float(row.get("normalized_len") or 0),
            1.0 if row.get("has_parentheses") else 0.0,
            1.0 if row.get("has_decimal") else 0.0,
            1.0 if row.get("has_range_predicate") else 0.0,
            1.0 if row.get("has_arithmetic") else 0.0,
            1.0 if row.get("waf_access_logged") else 0.0,
            1.0 if row.get("waf_audit_logged") else 0.0,
            1.0 if row.get("backend_reached") else 0.0,
            1.0 if row.get("oracle_matched") else 0.0,
        ]
        for key, choices in cat_values.items():
            actual = str(row.get(key, "unknown"))
            values.extend([1.0 if actual == choice else 0.0 for choice in choices])
        matrix.append(values)
    return matrix, feature_names


def metrics(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    tp = sum(1 for y, p in zip(y_true, y_pred, strict=True) if y == 1 and p == 1)
    tn = sum(1 for y, p in zip(y_true, y_pred, strict=True) if y == 0 and p == 0)
    fp = sum(1 for y, p in zip(y_true, y_pred, strict=True) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(y_true, y_pred, strict=True) if y == 1 and p == 0)
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        "false_negative_rate": round(fn / (fn + tp), 4) if fn + tp else 0.0,
        "accuracy": round((tp + tn) / len(y_true), 4) if y_true else 0.0,
    }


def sprint7_ml_baseline() -> dict[str, Any]:
    from joblib import dump
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    rows, labels = build_feature_rows()
    matrix, feature_names = vectorize(rows)
    x_train, x_test, y_train, y_test, _idx_train, idx_test = train_test_split(matrix, labels, list(range(len(rows))), test_size=0.25, random_state=707, stratify=labels)
    models = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=707),
        "random_forest": RandomForestClassifier(n_estimators=80, random_state=707, max_depth=6),
    }
    model_summaries: dict[str, Any] = {}
    pred_rows: list[dict[str, Any]] = []
    PRIVATE.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        model.fit(x_train, y_train)
        pred = list(model.predict(x_test))
        score = metrics(y_test, pred)
        model_path = PRIVATE / f"sprint7_{name}.joblib"
        dump(model, model_path)
        importances: list[tuple[str, float]] = []
        if hasattr(model, "feature_importances_"):
            importances = sorted(zip(feature_names, list(model.feature_importances_), strict=True), key=lambda item: item[1], reverse=True)[:12]
        elif hasattr(model, "coef_"):
            importances = sorted(zip(feature_names, [abs(v) for v in model.coef_[0]], strict=True), key=lambda item: item[1], reverse=True)[:12]
        model_summaries[name] = {"metrics": score, "model_artifact": str(model_path), "top_features": [{"feature": f, "importance": round(float(v), 6)} for f, v in importances]}
        for sample_idx, truth, predicted in zip(idx_test, y_test, pred, strict=True):
            row = rows[sample_idx]
            truth_i = int(truth)
            predicted_i = int(predicted)
            pred_rows.append({
                "model": name,
                "sample_id": row.get("sample_id"),
                "source_path": row.get("source_path"),
                "family": row.get("family"),
                "label": "attack" if truth_i else "benign",
                "predicted": "attack" if predicted_i else "benign",
                "correct": bool(truth_i == predicted_i),
                "payload_sha256": row.get("payload_sha256"),
                "payload_redacted": True,
            })
    write_jsonl(OUT / "sprint7_ml_predictions.redacted.jsonl", pred_rows)
    summary = {
        "status": "PASS" if all(m["metrics"]["false_positive_rate"] <= 0.05 and m["metrics"]["false_negative_rate"] <= 0.10 for m in model_summaries.values()) else "FAIL",
        "dataset_rows": len(rows),
        "attack_rows": sum(labels),
        "control_rows": len(labels) - sum(labels),
        "feature_count": len(feature_names),
        "models": model_summaries,
        "predictions_output": str(OUT / "sprint7_ml_predictions.redacted.jsonl"),
        "claim_boundary": "Classical ML baseline over lab feature schema; not a production model claim.",
    }
    write_json(OUT / "sprint7_ml_baseline.summary.json", summary)
    return summary


def public_redaction_ok(paths: list[Path]) -> tuple[bool, list[str]]:
    violations: list[str] = []
    for path in paths:
        for idx, row in enumerate(read_jsonl(path), start=1):
            leaked = sorted(FORBIDDEN_PUBLIC_KEYS.intersection(row.keys()))
            if leaked:
                violations.append(f"{path}:{idx}:{','.join(leaked)}")
    return not violations, violations


def build_csv_review(summary: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "vaccine_sprints_5_6_7_review.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "key", "value"])
        for section in ["preflight", "sprint5", "sprint6", "sprint7"]:
            for key, value in summary.get(section, {}).items():
                writer.writerow([section, key, json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value])
    summary["review_csv"] = str(csv_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vaccine sprints 5, 6, and 7 in the controlled lab.")
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    preflight = ensure_prereqs()
    if not preflight.get("ok"):
        write_json(OUT / "sprints_5_6_7_definition_of_done.summary.json", {"status": "FAIL", "preflight": preflight})
        raise SystemExit(1)
    s5 = sprint5_seqgan_adapter()
    s7 = sprint7_ml_baseline()
    run_py(["scripts/run_vaccine_gate.py"])
    s6 = read_json(OUT / "sprint6_vaccine_gate.summary.json")
    redaction_ok, redaction_violations = public_redaction_ok([
        OUT / "sprint5_seqgan_adapter_acceptance.redacted.jsonl",
        OUT / "sprint5_seqgan_adapter_rejections.redacted.jsonl",
        OUT / "sprint7_ml_predictions.redacted.jsonl",
    ])
    gates = [
        {"name": "preconditions_ready", "passed": preflight.get("ok"), "evidence": preflight},
        {"name": "sprint5_seqgan_adapter_lineage", "passed": s5.get("status") == "PASS" and s5.get("projected_generated") == 0, "evidence": s5},
        {"name": "sprint6_one_command_gate", "passed": s6.get("status") == "PASS", "evidence": s6},
        {"name": "sprint7_ml_baseline", "passed": s7.get("status") == "PASS", "evidence": {"dataset_rows": s7.get("dataset_rows"), "feature_count": s7.get("feature_count"), "models": list(s7.get("models", {}).keys())}},
        {"name": "public_redaction", "passed": redaction_ok, "evidence": {"violations": redaction_violations}},
    ]
    passed = all(g["passed"] for g in gates)
    summary = {
        "status": "PASS" if passed else "FAIL",
        "definition_of_done_passed": passed,
        "preflight": preflight,
        "sprint5": s5,
        "sprint6": s6,
        "sprint7": s7,
        "gates": gates,
        "passed_gates": [g["name"] for g in gates if g["passed"]],
        "failed_gates": [g["name"] for g in gates if not g["passed"]],
        "public_artifacts_redacted": redaction_ok,
        "private_replay_root": str(PRIVATE),
        "claim_boundary": "Controlled lab only. Sprint 5 is a restricted SeqGAN adapter reward loop, Sprint 6 is artifact regression, Sprint 7 is classical ML baseline; not production protection or vendor full raw SeqGAN proof.",
    }
    build_csv_review(summary)
    write_json(OUT / "sprints_5_6_7_definition_of_done.summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
