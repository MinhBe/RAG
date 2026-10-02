from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str = Field(default_factory=lambda: f"F-{uuid4().hex[:12]}")
    disposition: Literal["benign", "suspicious", "escalate", "insufficient_evidence"]
    severity: Literal["low", "medium", "high", "critical"]
    title: str = Field(min_length=1, max_length=256)
    evidence_refs: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=4096)
    detector: str = Field(min_length=1, max_length=128)
    validation_status: Literal["draft", "validated"] = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
