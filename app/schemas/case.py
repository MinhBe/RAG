from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import Evidence


class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^CASE-[A-Za-z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4096)
    submitted_by: str = Field(default="tier1_demo_user", min_length=1, max_length=128)
    environment: Literal["synthetic", "redacted", "lab"] = "synthetic"
    evidence: list[Evidence] = Field(min_length=1, max_length=100)
    schema_version: Literal["1.0"] = "1.0"


class AnalystDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2048)
    severity: Literal["low", "medium", "high", "critical"]
    evidence_refs: list[str]
    affected_assets: list[str]
    recommended_action: str = Field(min_length=1, max_length=2048)
    decision_options: list[Literal["escalate", "close", "need_more_evidence"]]
    safety_boundaries: list[str]
