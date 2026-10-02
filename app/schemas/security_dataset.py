from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeqGANSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1, max_length=128)
    generator_version: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    source_dataset_version: str = Field(min_length=1, max_length=128)
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attack_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    y_level: Literal["Y1", "Y2", "Y3", "Y4"]
    module_id: str = Field(min_length=1, max_length=128)
    root_grammar_id: str = Field(min_length=1, max_length=128)
    structure_cell_id: str = Field(min_length=1, max_length=128)
    boolean_pair_id: str = Field(min_length=1, max_length=128)
    expected_truth: Literal["TRUE", "FALSE"]
    split: Literal["train", "validation", "frozen_test", "generated"]
    payload_ref: str | None = Field(
        default=None,
        description="Opaque local reference only; do not expose raw payload in public artifacts.",
    )
    contract_valid: bool
    runtime_claim_allowed: bool = False
    postgres_parse_status: Literal["not_run", "passed", "failed"] = "not_run"
    postgres_runtime_status: Literal["not_run", "passed", "failed"] = "not_run"
    truth_oracle_status: Literal["not_run", "matched", "mismatched", "inconclusive"] = "not_run"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def runtime_claim_requires_runtime(self) -> SeqGANSample:
        if self.runtime_claim_allowed:
            if self.postgres_runtime_status != "passed":
                raise ValueError("runtime claims require passed PostgreSQL runtime status")
            if self.truth_oracle_status != "matched":
                raise ValueError("runtime claims require matched truth oracle status")
        return self


class LabExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab_execution_id: str = Field(min_length=1, max_length=128)
    sample_id: str = Field(min_length=1, max_length=128)
    lab_profile: str = Field(min_length=1, max_length=128)
    vm_name: str = Field(min_length=1, max_length=128)
    vm_snapshot: str = Field(min_length=1, max_length=128)
    network_mode: Literal["host_only", "nat_provisioning", "isolated"]
    started_at: datetime
    finished_at: datetime | None = None
    execution_status: Literal["planned", "running", "completed", "failed", "skipped"]
    cleanup_status: Literal["not_required", "pending", "completed", "failed"] = "pending"


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    lab_execution_id: str = Field(min_length=1, max_length=128)
    source: Literal["modsecurity", "suricata", "postgres", "auditd", "journald", "atomic", "synthetic"]
    observed_at: datetime
    severity: Literal["low", "medium", "high", "critical", "info"]
    message: str = Field(min_length=1, max_length=16384)
    evidence_ref: str = Field(min_length=1, max_length=128)
    redaction_status: Literal["synthetic", "redacted"] = "synthetic"
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
