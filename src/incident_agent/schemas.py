"""Structured contracts between agents. Every agent output is validated against one of these."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RootCauseCategory = Literal[
    "bad_config",
    "schema_migration",
    "code_bug",
    "performance_regression",
    "resource_exhaustion",
    "dependency_failure",
    "certificate_expiry",
    "unknown",
]

SpecialistName = Literal["logs", "changes", "metrics", "docs"]

ALL_SPECIALISTS: tuple[SpecialistName, ...] = ("logs", "changes", "metrics", "docs")


class TriageResult(BaseModel):
    incident_type: str = Field(description="Short label, e.g. 'elevated 5xx errors', 'latency'")
    service: str = Field(description="Primary affected service name as known to the platform")
    time_hint: str | None = Field(default=None, description="When it started, if stated")
    specialists: list[SpecialistName] = Field(default_factory=lambda: list(ALL_SPECIALISTS))
    rationale: str = ""


class Finding(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    significance: Literal["high", "medium", "low"] = "medium"


class SpecialistReport(BaseModel):
    summary: str
    findings: list[Finding] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str = Field(description="ID of the tool output this is drawn from, e.g. E3")
    source: str = Field(description="logs | deployments | metrics | docs | services")
    detail: str = Field(description="The concrete fact observed, quoting key values")


class RootCause(BaseModel):
    hypothesis: str
    category: RootCauseCategory
    confidence: float = Field(ge=0.0, le=1.0)


class NextStep(BaseModel):
    action: str
    priority: Literal["P0", "P1", "P2"]
    rationale: str = ""


class IncidentReport(BaseModel):
    summary: str
    incident_type: str
    affected_services: list[str]
    evidence: list[EvidenceItem]
    root_cause: RootCause
    caused_by_latest_deploy: bool | None = Field(
        description="True if the latest deploy caused it, false if not, null if undetermined"
    )
    alternatives_ruled_out: list[str] = Field(default_factory=list)
    next_steps: list[NextStep]
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("caused_by_latest_deploy", mode="before")
    @classmethod
    def _null_string(cls, v):
        # The prompt template shows "<true | false | null>"; models sometimes echo it as text.
        return (
            None if isinstance(v, str) and v.strip().lower() in ("null", "none", "unknown") else v
        )


class CriticVerdict(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
