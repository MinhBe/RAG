import json

import httpx

from app.core.settings import settings
from app.providers.ai.analyst import CaseAnalystProvider
from app.schemas.case import AnalystDraft, CaseRecord
from app.schemas.evidence import Evidence


def _case() -> CaseRecord:
    return CaseRecord(
        case_id="CASE-LLM-001",
        title="LLM provider unit case",
        evidence=[
            Evidence(
                evidence_id="EV-LLM-001",
                source="synthetic",
                event_type="auth",
                severity_hint="high",
                message="Synthetic high-severity event.",
            )
        ],
    )


def _draft() -> AnalystDraft:
    return AnalystDraft(
        summary="deterministic fallback",
        severity="high",
        evidence_refs=["EV-LLM-001"],
        affected_assets=["UNKNOWN_OR_REDACTED_ASSET"],
        recommended_action="human review",
        decision_options=["escalate", "close", "need_more_evidence"],
        safety_boundaries=["no_autonomous_remediation"],
    )


def test_provider_accepts_fenced_json(monkeypatch):
    monkeypatch.setattr(settings, "hermes_a_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    body = {
        "summary": "LLM draft summary",
        "severity": "high",
        "evidence_refs": ["EV-LLM-001"],
        "affected_assets": ["UNKNOWN_OR_REDACTED_ASSET"],
        "recommended_action": "Review evidence; do not remediate automatically.",
        "decision_options": ["escalate", "close", "need_more_evidence"],
        "safety_boundaries": ["no_autonomous_remediation"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "```json\n" + json.dumps(body) + "\n```"}}
                ]
            },
        )

    provider = CaseAnalystProvider(transport=httpx.MockTransport(handler))
    draft, metadata = provider.draft(_case(), [], _draft())
    assert metadata["draft_source"] == "9router_llm"
    assert draft.summary == "LLM draft summary"


def test_provider_falls_back_on_unknown_evidence_ref(monkeypatch):
    monkeypatch.setattr(settings, "hermes_a_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_model", "test-model")
    bad_body = {
        "summary": "bad ref",
        "severity": "high",
        "evidence_refs": ["EV-NOT-SUBMITTED"],
        "affected_assets": ["UNKNOWN_OR_REDACTED_ASSET"],
        "recommended_action": "Review evidence.",
        "decision_options": ["escalate", "close", "need_more_evidence"],
        "safety_boundaries": ["no_autonomous_remediation"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(bad_body)}}]},
        )

    provider = CaseAnalystProvider(transport=httpx.MockTransport(handler))
    draft, metadata = provider.draft(_case(), [], _draft())
    assert metadata["draft_source"] == "deterministic_fallback"
    assert metadata["error_type"] == "ValueError"
    assert draft.summary == "deterministic fallback"
