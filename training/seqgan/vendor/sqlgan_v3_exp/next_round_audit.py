# ruff: noqa
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

RUNTIME_SAFE_FALSE = {"runtime_claim_allowed": False, "exploit_confirmed": False}
RAW_PAYLOAD_FILES = {"generated_candidates.csv", "accepted_for_next_stage.csv", "rejected_for_next_stage.csv"}


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def classify_log(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")[-8000:] if path.exists() else ""
    low = text.lower()
    if "cuda out of memory" in low or "outofmemoryerror" in low:
        return "cuda_oom"
    if "filenotfounderror" in low or "no such file" in low:
        return "missing_file"
    if "traceback" in low:
        return "python_error"
    return "none"


def collect_run_outputs(out_dir: str | Path, *, plan_csv: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out = Path(out_dir)
    plan = pd.read_csv(plan_csv) if plan_csv and Path(plan_csv).exists() else pd.DataFrame()
    status_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []

    run_dirs = [p for p in out.iterdir() if p.is_dir()] if out.exists() else []
    for rd in sorted(run_dirs):
        log = rd / "_run_stdout.log"
        summaries = list(rd.rglob("run_summary.json"))
        gen_files = list(rd.rglob("generated_candidates.csv"))
        acc_files = list(rd.rglob("accepted_for_next_stage.csv"))
        code_match = re.search(r"(G\d(?:-[A-Z]\d+)?-I\d+|G\d-I\d+)", rd.name)
        run_code = code_match.group(1) if code_match else rd.name
        status_rows.append({
            "run_dir": rd.name,
            "run_code": run_code,
            "summary_count": len(summaries),
            "generated_candidate_files": len(gen_files),
            "accepted_files": len(acc_files),
            "log_error_class": classify_log(log),
        })
        for sp in summaries:
            s = _safe_read_json(sp)
            g = s.get("generated", {}) if isinstance(s, dict) else {}
            summary_rows.append({
                "run_dir": rd.name,
                "run_code": run_code,
                "summary_path": str(sp.relative_to(out)),
                "direction": s.get("direction"),
                "tokenizer": s.get("tokenizer"),
                "best_mle_nll": s.get("best_mle_nll"),
                "seconds_total": s.get("seconds_total"),
                "runtime_claim_allowed": bool(s.get("runtime_claim_allowed", False)),
                "exploit_confirmed": bool(s.get("exploit_confirmed", False)),
                "gen_rows": g.get("rows"),
                "gen_accepted": g.get("accepted"),
                "gen_accepted_rate": g.get("accepted_rate"),
                "gen_duplicate_rate": g.get("duplicate_rate"),
                "gen_contract_valid_rate": g.get("contract_valid_rate"),
                "gen_required_tokens_rate": g.get("required_tokens_rate"),
                "gen_raw_parserlike_clean_rate": g.get("raw_parserlike_clean_rate"),
                "gen_parserlike_clean_rate": g.get("parserlike_clean_rate"),
                "gen_repair_action_count_mean": g.get("repair_action_count_mean"),
                "gen_accepted_root_coverage": g.get("accepted_root_coverage"),
                "gen_accepted_cell_coverage": g.get("accepted_cell_coverage"),
            })
        for ap in acc_files:
            df = _read_csv(ap)
            row = {"run_dir": rd.name, "run_code": run_code, "accepted_path": str(ap.relative_to(out)), "accepted_rows": len(df)}
            for col in ["runtime_claim_allowed", "exploit_confirmed", "parserlike_clean", "raw_parserlike_clean"]:
                row[f"{col}_rate"] = float(df[col].fillna(False).astype(bool).mean()) if col in df.columns and len(df) else 0.0
            if "repair_action_count" in df.columns and len(df):
                row["repair_action_count_mean"] = float(pd.to_numeric(df["repair_action_count"], errors="coerce").fillna(0).mean())
            if "payload" in df.columns and len(df):
                row["unique_payloads"] = int(df["payload"].astype(str).nunique())
                row["duplicate_payload_rows"] = int(len(df) - row["unique_payloads"])
            if "root_id" in df.columns and len(df):
                row["accepted_root_coverage_csv"] = int(df["root_id"].astype(str).nunique())
            if "structure_cell_id" in df.columns and len(df):
                row["accepted_cell_coverage_csv"] = int(df["structure_cell_id"].astype(str).nunique())
            accepted_rows.append(row)
    status = pd.DataFrame(status_rows)
    summaries = pd.DataFrame(summary_rows)
    accepted = pd.DataFrame(accepted_rows)
    if not plan.empty and "run_code" in plan.columns:
        expected = set(plan["run_code"].astype(str))
        seen = set(status.get("run_code", pd.Series(dtype=str)).astype(str))
        missing = sorted(expected - seen)
        if missing:
            status = pd.concat([status, pd.DataFrame([{"run_code": m, "run_dir": "MISSING", "summary_count": 0, "generated_candidate_files": 0, "accepted_files": 0, "log_error_class": "missing_run_dir"} for m in missing])], ignore_index=True)
    return status, summaries, accepted


def write_audit_report(out_dir: str | Path, report_dir: str | Path, *, plan_csv: str | Path | None = None) -> dict[str, str]:
    report = Path(report_dir)
    report.mkdir(parents=True, exist_ok=True)
    status, summaries, accepted = collect_run_outputs(out_dir, plan_csv=plan_csv)
    status.to_csv(report / "next_round_run_status.csv", index=False)
    summaries.to_csv(report / "next_round_run_summaries.csv", index=False)
    accepted.to_csv(report / "next_round_accepted_audit.csv", index=False)

    leaderboard = summaries.copy()
    if not leaderboard.empty:
        for c in ["gen_accepted_rate", "gen_raw_parserlike_clean_rate", "gen_contract_valid_rate", "gen_required_tokens_rate", "gen_duplicate_rate", "gen_repair_action_count_mean"]:
            leaderboard[c] = pd.to_numeric(leaderboard.get(c), errors="coerce").fillna(0)
        leaderboard["static_reality_score"] = (
            2.0 * leaderboard["gen_accepted_rate"]
            + 1.5 * leaderboard["gen_raw_parserlike_clean_rate"]
            + 1.5 * leaderboard["gen_contract_valid_rate"]
            + 1.0 * leaderboard["gen_required_tokens_rate"]
            - 1.5 * leaderboard["gen_duplicate_rate"]
            - 1.0 * leaderboard["gen_repair_action_count_mean"]
        )
        leaderboard = leaderboard.sort_values("static_reality_score", ascending=False)
    leaderboard.to_csv(report / "next_round_static_leaderboard.csv", index=False)

    total = len(status)
    ok = int((status.get("summary_count", pd.Series(dtype=int)).fillna(0).astype(int) > 0).sum()) if total else 0
    failed = total - ok
    runtime_any = bool(summaries.get("runtime_claim_allowed", pd.Series(dtype=bool)).fillna(False).astype(bool).any()) if len(summaries) else False
    exploit_any = bool(summaries.get("exploit_confirmed", pd.Series(dtype=bool)).fillna(False).astype(bool).any()) if len(summaries) else False
    md = [
        "# SQLGAN V3 Next Round Static Audit",
        "",
        "## Boundary",
        "Offline/static structure-learning only. No live target, no sqlmap, no WAF bypass, no exfiltration. PostgreSQL evidence must be local sandbox evidence and still is not exploit confirmation.",
        "",
        "## Run status",
        f"- run_dirs_or_expected: `{total}`",
        f"- completed_with_summary: `{ok}`",
        f"- missing_or_failed: `{failed}`",
        f"- runtime_claim_allowed_any: `{runtime_any}`",
        f"- exploit_confirmed_any: `{exploit_any}`",
        "",
        "## Interpretation",
        "Grammar/contract and parser-like clean metrics are static/offline metrics. They can select candidates for local PostgreSQL sandbox parsing, but they do not prove exploitability.",
    ]
    (report / "NEXT_ROUND_STATIC_AUDIT_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    return {"report_dir": str(report), "leaderboard": str(report / "next_round_static_leaderboard.csv")}
