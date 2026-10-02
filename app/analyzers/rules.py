from app.schemas.evidence import Evidence
from app.schemas.finding import Finding


def route_for_review(evidence: Evidence) -> Finding | None:
    if evidence.severity_hint not in {"high", "critical"}:
        return None
    return Finding(
        disposition="escalate",
        severity=evidence.severity_hint,
        title="High-severity source hint requires analyst review",
        evidence_refs=[evidence.evidence_id],
        rationale="Routing rule only; it does not assert that a threat is confirmed.",
        detector="severity_hint_review_router_v1",
        validation_status="validated",
    )
