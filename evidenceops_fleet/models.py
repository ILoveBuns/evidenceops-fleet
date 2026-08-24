from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


Decision = Literal["ready", "blocked"]
OperationStatus = Literal["queued", "running", "ready", "blocked", "failed"]


class EvidenceItem(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    value: str = Field(min_length=1, max_length=10_000)
    source: str = Field(min_length=3, max_length=500)


class EvidenceCaseCreate(BaseModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,63}$")
    objective: str = Field(min_length=10, max_length=500)
    required_evidence: list[str] = Field(min_length=1, max_length=20)
    evidence: list[EvidenceItem] = Field(max_length=50)


class GitHubOperationCreate(BaseModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,63}$")
    objective: str = Field(min_length=10, max_length=500)
    repository: str = Field(
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=200
    )
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{7,40}$")


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


class ApprovalCreate(BaseModel):
    approval_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,63}$")
    actor_label: str = Field(min_length=2, max_length=200)
    note: str = Field(min_length=5, max_length=500)


class ApprovalReceipt(BaseModel):
    approval_id: str
    case_id: str
    evidence_digest: str
    actor_digest: str
    note_digest: str
    receipt_digest: str
    created_at: datetime


class AgentBrief(BaseModel):
    case_id: str
    source_decision: Decision
    source_evidence_digest: str
    model: str
    brief: str
    final_author: str
    event_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryEvent(BaseModel):
    event_type: Literal["case", "operation", "approval", "brief"]
    event_id: str
    recorded_at: datetime
    digest: str
    status: str


class CaseMemorySnapshot(BaseModel):
    schema_name: Literal["evidenceops-case-memory/v1"] = "evidenceops-case-memory/v1"
    case_id: str
    retention_policy: Literal["no-ttl-configured"] = "no-ttl-configured"
    raw_evidence_included: Literal[False] = False
    events: list[MemoryEvent]


class AgentRegistration(BaseModel):
    name: str
    role: str
    version: str
    lifecycle_status: Literal["approved", "experimental", "retired"]
    framework: str
    capabilities: list[str]
    input_boundary: str
    owner_department: str
    approved_consumers: list[str]
    data_classifications: list[str]
    allowed_regions: list[str]
    model: str | None = None
    deterministic: bool


class WorkflowNodeRegistration(BaseModel):
    name: str
    kind: Literal["llm-agent", "deterministic-authority"]
    responsibility: str


class WorkflowRegistration(BaseModel):
    schema_name: Literal["evidenceops-workflow/v1"] = "evidenceops-workflow/v1"
    framework: Literal["google-adk"] = "google-adk"
    purpose: str
    nodes: list[WorkflowNodeRegistration]
    edges: list[tuple[str, str]]
    decision_authority: str


class EvidenceOperation(BaseModel):
    operation_id: str
    case_id: str
    input_digest: str
    status: OperationStatus
    decision: Decision | None = None
    evidence_digest: str | None = None
    error_code: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    lease_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
