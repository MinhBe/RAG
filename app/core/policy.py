def review_policy(findings: list[dict]) -> dict:
    if findings:
        return {
            "approval_required": True,
            "approval_status": "pending_human_review",
        }
    return {
        "approval_required": False,
        "approval_status": "not_required",
    }
