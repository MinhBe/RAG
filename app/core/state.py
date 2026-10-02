from typing import TypedDict


class HermesState(TypedDict, total=False):
    request_id: str
    evidence: list[dict]
    findings: list[dict]
    errors: list[str]
    approval_required: bool
    approval_status: str
