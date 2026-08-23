from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Decision = Literal["ready", "blocked"]


class EvidenceItem(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    value: str = Field(min_length=1, max_length=10_000)
    source: str = Field(min_length=3, max_length=500)


class EvidenceCaseCreate(BaseModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,63}$")
    objective: str = Field(min_length=10, max_length=500)
    required_evidence: list[str] = Field(min_length=1, max_length=20)
    evidence: list[EvidenceItem] = Field(max_length=50)


class AgentTrace(BaseModel):
    agent: str
    outcome: str
    detail: str


class EvidenceCaseResult(BaseModel):
    case_id: str
    decision: Decision
    evidence_digest: str
    missing: list[str]
    conflicts: list[str]
    next_action: str
    traces: list[AgentTrace]
    created_at: datetime


class AgentRegistration(BaseModel):
    name: str
    role: str
    model: str | None = None
    deterministic: bool

