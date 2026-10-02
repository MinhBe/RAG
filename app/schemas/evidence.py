from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(
        default_factory=lambda: f"EV-{uuid4().hex[:12]}",
        pattern=r"^EV-[A-Za-z0-9_-]{1,64}$",
    )
    source: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=1, max_length=128)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    severity_hint: Literal["low", "medium", "high", "critical"] | None = None
    message: str = Field(min_length=1, max_length=16384)
    attributes: dict[str, Any] = Field(default_factory=dict)
    redaction_status: Literal["synthetic", "redacted"] = "synthetic"
    schema_version: Literal["1.0"] = "1.0"
