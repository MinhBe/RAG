
from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

LEAD_BRIEF_EXTRACTION_PROMPT = """You are the Hermes Lead intake extractor.
Return JSON only. Distinguish user-stated facts from inferred facts.
Never invent unsupported requirements. Use null or [] when missing.
Required schema: trace_id, user_text, objective, constraints, deliverable,
audience, urgency, case_hint, role_hints, risks, source_spans.
Only the Lead bot may run this intake step.
"""


class StatedInferredText(BaseModel):
    stated: str | None = None
    inferred: str | None = None


class StatedInferredList(BaseModel):
    stated: list[str] = Field(default_factory=list)
    inferred: list[str] = Field(default_factory=list)


class Brief(BaseModel):
    trace_id: str
    user_text: str
    objective: StatedInferredText
    constraints: StatedInferredList = Field(default_factory=StatedInferredList)
    deliverable: StatedInferredText = Field(default_factory=StatedInferredText)
    audience: StatedInferredText = Field(default_factory=StatedInferredText)
    urgency: StatedInferredText = Field(default_factory=StatedInferredText)
    case_hint: str | None = None
    role_hints: list[str] = Field(default_factory=list)
    risks: StatedInferredList = Field(default_factory=StatedInferredList)
    source_spans: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class BriefValidationResult:
    ok: bool
    brief: Brief | None = None
    errors: tuple[str, ...] = ()


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def validate_brief_payload(payload: dict) -> BriefValidationResult:
    try:
        brief = Brief.model_validate(payload)
    except ValidationError as exc:
        return BriefValidationResult(ok=False, errors=tuple(str(error) for error in exc.errors()))
    return BriefValidationResult(ok=True, brief=brief)


def validate_brief_json(raw_json: str) -> BriefValidationResult:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return BriefValidationResult(ok=False, errors=(f"invalid_json: {exc}",))
    if not isinstance(payload, dict):
        return BriefValidationResult(ok=False, errors=("brief JSON must be an object",))
    return validate_brief_payload(payload)


def minimal_brief_from_text(user_text: str, case_hint: str | None = None) -> Brief:
    return Brief(
        trace_id=new_trace_id(),
        user_text=user_text,
        objective=StatedInferredText(stated=user_text.strip() or None, inferred=None),
        case_hint=case_hint,
        source_spans=[user_text],
    )
