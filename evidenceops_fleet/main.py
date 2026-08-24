import hmac
from os import getenv

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from .dashboard import DASHBOARD_HTML
from .approval import create_receipt
from .brief import AdkBriefService
from .models import (
    AgentRegistration,
    WorkflowNodeRegistration,
    WorkflowRegistration,
    AgentBrief,
    ApprovalCreate,
    ApprovalReceipt,
    CaseMemorySnapshot,
    EvidenceCaseCreate,
    EvidenceCaseResult,
    EvidenceOperation,
    GitHubOperationCreate,
    MemoryEvent,
)
from .github_evidence import GitHubEvidenceAdapter, GitHubEvidenceError
from .operations import (
    OperationBusyError,
    cloud_tasks_config,
    enqueue_cloud_task,
    process_operation,
    queued_operation,
    task_authorized,
)
from .service import EvidenceFleet
from .store import ResultStore, configured_store


app = FastAPI(title="EvidenceOps Fleet", version="0.1.0")
store = configured_store()
brief_service = AdkBriefService()
github_adapter = GitHubEvidenceAdapter()


def get_store() -> ResultStore:
    return store


def get_brief_service() -> AdkBriefService:
    return brief_service


def get_github_adapter() -> GitHubEvidenceAdapter:
    return github_adapter


def operation_runtime() -> str:
    if getenv("EVIDENCEOPS_TASKS_QUEUE"):
        return "cloud-tasks"
    if getenv("EVIDENCEOPS_STORE") == "firestore":
        return "misconfigured"
    return "local-background"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidenceops-fleet"}


@app.get("/runtime")
def runtime() -> dict[str, str | bool]:
    vertex_enabled = getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
    return {
        "store": "firestore"
        if getenv("EVIDENCEOPS_STORE") == "firestore"
        else "memory",
        "gemini_ready": bool(getenv("GOOGLE_API_KEY")) or vertex_enabled,
        "approval_guard": "secret" if getenv("EVIDENCEOPS_APPROVAL_TOKEN") else "demo-only",
        "brief_guard": "public-demo"
        if getenv("EVIDENCEOPS_PUBLIC_DEMO_BRIEFS", "").lower() == "true"
        else "secret",
        "worker_guard": "secret"
        if getenv("EVIDENCEOPS_TASK_TOKEN")
        else "local-only",
        "operation_runtime": operation_runtime(),
    }


def agent_catalog() -> list[AgentRegistration]:
    shared_consumers = ["release-engineering", "compliance", "internal-audit"]
    shared_regions = ["us-central1"]
    return [
        AgentRegistration(
            name="intake",
            role="source-bound fact intake",
            version="1.0.0",
            lifecycle_status="approved",
            framework="google-adk",
            capabilities=["normalize-source-attributed-evidence"],
            input_boundary="case metadata and source-attributed evidence",
            owner_department="platform-security",
            approved_consumers=shared_consumers,
            data_classifications=["source-metadata", "confidential-digests"],
            allowed_regions=shared_regions,
            model="gemini-3.5-flash",
            deterministic=False,
        ),
        AgentRegistration(
            name="policy",
            role="missing and conflict checks",
            version="1.0.0",
            lifecycle_status="approved",
            framework="google-adk",
            capabilities=["detect-missing-evidence", "detect-source-conflicts"],
            input_boundary="case metadata and deterministic policy results",
            owner_department="compliance",
            approved_consumers=shared_consumers,
            data_classifications=["policy-metadata", "confidential-digests"],
            allowed_regions=shared_regions,
            model="gemini-3.5-flash",
            deterministic=False,
        ),
        AgentRegistration(
            name="verifier",
            role="canonical SHA-256 binding",
            version="1.0.0",
            lifecycle_status="approved",
            framework="deterministic-python",
            capabilities=["canonicalize-evidence", "bind-sha256-digest"],
            input_boundary="canonical evidence payload",
            owner_department="platform-security",
            approved_consumers=shared_consumers,
            data_classifications=["confidential-digests"],
            allowed_regions=shared_regions,
            deterministic=True,
        ),
        AgentRegistration(
            name="supervisor",
            role="fail-closed routing and human boundary",
            version="1.0.0",
            lifecycle_status="approved",
            framework="google-adk",
            capabilities=["generate-redacted-action-brief", "route-human-approval"],
            input_boundary="persisted redacted result only; no raw evidence values",
            owner_department="release-engineering",
            approved_consumers=shared_consumers,
            data_classifications=["redacted-results", "confidential-digests"],
            allowed_regions=shared_regions,
            model="gemini-3.5-flash",
            deterministic=False,
        ),
    ]


@app.get("/agents", response_model=list[AgentRegistration])
def agents(
    department: str | None = Query(default=None, min_length=2, max_length=80),
    capability: str | None = Query(default=None, min_length=2, max_length=100),
) -> list[AgentRegistration]:
    catalog = agent_catalog()
    if department:
        catalog = [
            agent
            for agent in catalog
            if department == agent.owner_department
            or department in agent.approved_consumers
        ]
    if capability:
        catalog = [agent for agent in catalog if capability in agent.capabilities]
    return catalog


@app.get("/workflow", response_model=WorkflowRegistration)
def workflow() -> WorkflowRegistration:
    return WorkflowRegistration(
        purpose="redacted post-decision brief and human-action routing",
        nodes=[
            WorkflowNodeRegistration(
                name="intake_agent",
                kind="llm-agent",
                responsibility="summarize source-bound persisted result metadata",
            ),
            WorkflowNodeRegistration(
                name="policy_agent",
                kind="llm-agent",
                responsibility="recheck blocked state through deterministic policy tool",
            ),
            WorkflowNodeRegistration(
                name="supervisor_agent",
                kind="llm-agent",
                responsibility="produce advisory next steps behind a human boundary",
            ),
            WorkflowNodeRegistration(
                name="deterministic_verifier",
                kind="deterministic-authority",
                responsibility="own missing, conflict, decision, and digest authority",
            ),
        ],
        edges=[
            ("START", "intake_agent"),
            ("intake_agent", "policy_agent"),
            ("policy_agent", "supervisor_agent"),
        ],
        decision_authority=(
            "deterministic_verifier executes before the ADK brief workflow; "
            "LLM agents cannot mutate its decision or evidence digest"
        ),
    )


@app.post("/cases", response_model=EvidenceCaseResult, status_code=201)
def run_case(
    payload: EvidenceCaseCreate, result_store: ResultStore = Depends(get_store)
) -> EvidenceCaseResult:
    try:
        return EvidenceFleet(result_store).run(payload)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/operations", response_model=EvidenceOperation, status_code=202)
def create_operation(
    payload: EvidenceCaseCreate,
    background_tasks: BackgroundTasks,
    result_store: ResultStore = Depends(get_store),
) -> EvidenceOperation:
    cloud_queue_enabled = bool(getenv("EVIDENCEOPS_TASKS_QUEUE"))
    if getenv("EVIDENCEOPS_STORE") == "firestore" and not cloud_queue_enabled:
        raise HTTPException(
            status_code=503,
            detail="Cloud Tasks configuration is required with Firestore",
        )
    candidate = queued_operation(payload)
    if cloud_queue_enabled:
        try:
            cloud_tasks_config()
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    existing = result_store.get_operation(candidate.operation_id)
    try:
        operation = result_store.save_operation_once(candidate)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if existing is not None and existing.status in {"running", "ready", "blocked"}:
        return operation
    if existing is not None and existing.status == "queued" and not cloud_queue_enabled:
        return operation
    if cloud_queue_enabled:
        try:
            enqueue_cloud_task(operation, payload)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    else:
        background_tasks.add_task(process_operation, operation, payload, result_store)
    return operation


@app.post(
    "/integrations/github/operations",
    response_model=EvidenceOperation,
    status_code=202,
)
def create_github_operation(
    payload: GitHubOperationCreate,
    background_tasks: BackgroundTasks,
    result_store: ResultStore = Depends(get_store),
    adapter: GitHubEvidenceAdapter = Depends(get_github_adapter),
) -> EvidenceOperation:
    try:
        evidence_case = adapter.collect(payload)
    except GitHubEvidenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return create_operation(evidence_case, background_tasks, result_store)


@app.get("/operations/{operation_id}", response_model=EvidenceOperation)
def get_operation(
    operation_id: str, result_store: ResultStore = Depends(get_store)
) -> EvidenceOperation:
    operation = result_store.get_operation(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="operation not found")
    return operation


@app.post("/operations/{operation_id}/execute", response_model=EvidenceOperation)
def execute_operation(
    operation_id: str,
    payload: EvidenceCaseCreate,
    request: Request,
    result_store: ResultStore = Depends(get_store),
) -> EvidenceOperation:
    if getenv("EVIDENCEOPS_TASK_TOKEN") and not task_authorized(
        request.headers.get("x-task-token", "")
    ):
        raise HTTPException(status_code=403, detail="task authorization required")
    operation = result_store.get_operation(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="operation not found")
    if operation.case_id != payload.case_id:
        raise HTTPException(status_code=409, detail="operation case mismatch")
    try:
        return process_operation(operation, payload, result_store)
    except OperationBusyError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/cases/{case_id}", response_model=EvidenceCaseResult)
def get_case(
    case_id: str, result_store: ResultStore = Depends(get_store)
) -> EvidenceCaseResult:
    result = result_store.get(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    return result


@app.get("/cases/{case_id}/memory", response_model=CaseMemorySnapshot)
def get_case_memory(
    case_id: str, result_store: ResultStore = Depends(get_store)
) -> CaseMemorySnapshot:
    case = result_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    events = [
        MemoryEvent(
            event_type="case",
            event_id=case.case_id,
            recorded_at=case.created_at,
            digest=case.evidence_digest,
            status=case.decision,
        )
    ]
    operation = result_store.get_operation(f"operation-{case_id}")
    if operation is not None:
        events.append(
            MemoryEvent(
                event_type="operation",
                event_id=operation.operation_id,
                recorded_at=operation.updated_at,
                digest=operation.evidence_digest or operation.input_digest,
                status=operation.status,
            )
        )
    events.extend(
        MemoryEvent(
            event_type="approval",
            event_id=receipt.approval_id,
            recorded_at=receipt.created_at,
            digest=receipt.receipt_digest,
            status="approved",
        )
        for receipt in result_store.list_approvals(case_id)
    )
    brief = result_store.get_brief(case_id)
    if brief is not None:
        events.append(
            MemoryEvent(
                event_type="brief",
                event_id="action-brief",
                recorded_at=brief.created_at,
                digest=brief.source_evidence_digest,
                status=brief.source_decision,
            )
        )
    events.sort(key=lambda event: (event.recorded_at, event.event_type, event.event_id))
    return CaseMemorySnapshot(case_id=case_id, events=events)


@app.post("/cases/{case_id}/brief", response_model=AgentBrief)
async def generate_brief(
    case_id: str,
    request: Request,
    result_store: ResultStore = Depends(get_store),
    service: AdkBriefService = Depends(get_brief_service),
) -> AgentBrief:
    configured_token = getenv("EVIDENCEOPS_BRIEF_TOKEN")
    supplied_token = request.headers.get("x-brief-token", "")
    authorized = bool(configured_token) and hmac.compare_digest(
        supplied_token, configured_token
    )
    public_demo = (
        case_id.startswith("demo-")
        and getenv("EVIDENCEOPS_PUBLIC_DEMO_BRIEFS", "").lower() == "true"
    )
    if not authorized and not public_demo:
        raise HTTPException(status_code=403, detail="brief authorization required")
    result = result_store.get(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    existing = result_store.get_brief(case_id)
    if existing is not None:
        return existing
    try:
        return result_store.save_brief_once(await service.generate(result))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/cases/{case_id}/approvals", response_model=ApprovalReceipt, status_code=201
)
def approve_case(
    case_id: str,
    payload: ApprovalCreate,
    request: Request,
    result_store: ResultStore = Depends(get_store),
) -> ApprovalReceipt:
    configured_token = getenv("EVIDENCEOPS_APPROVAL_TOKEN")
    supplied_token = request.headers.get("x-approval-token", "")
    synthetic_demo = case_id.startswith("demo-") and payload.actor_label == (
        "synthetic-demo-reviewer"
    )
    authorized = bool(configured_token) and hmac.compare_digest(
        supplied_token, configured_token
    )
    if not authorized and not synthetic_demo:
        raise HTTPException(status_code=403, detail="approval authorization required")
    case = result_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    try:
        existing = result_store.get_approval(case_id, payload.approval_id)
        if existing is not None:
            candidate = create_receipt(case, payload, created_at=existing.created_at)
        else:
            candidate = create_receipt(case, payload)
        return result_store.save_approval_once(candidate)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
