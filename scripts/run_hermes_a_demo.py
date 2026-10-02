import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.case_pipeline import run_case_pipeline
from app.schemas.case import CaseRecord

SAMPLE_PATH = REPO_ROOT / "data/public/hermes_a_sample_case.json"


def main() -> None:
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8-sig"))
    case = CaseRecord.model_validate(payload["case"])
    result = run_case_pipeline(case)
    print("Hermes A case", result["case_id"])
    print("status", result["case_status"])
    print("approval", result["approval_status"])
    print("findings", len(result["findings"]))
    print("json_report", result["report_json_path"])
    print("html_report", result["report_html_path"])
    if result["remediation_executed"] is not False:
        raise SystemExit("FAIL: remediation boundary violated")
    print("PASS Hermes A core post-audit demo")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
