import hmac
from os import getenv

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .dashboard import DASHBOARD_HTML
from .approval import create_receipt
from .brief import AdkBriefService
from .models import (
    AgentRegistration,
    AgentBrief,
    ApprovalCreate,
    ApprovalReceipt,
    EvidenceCaseCreate,
    EvidenceCaseResult,
)
from .service import EvidenceFleet
from .store import ResultStore, configured_store


app = FastAPI(title="EvidenceOps Fleet", version="0.1.0")
store = configured_store()
brief_service = AdkBriefService()


def get_store() -> ResultStore:
    return store


def get_brief_service() -> AdkBriefService:
    return brief_service


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
    }


@app.get("/agents", response_model=list[AgentRegistration])
def agents() -> list[AgentRegistration]:
    return [
        AgentRegistration(
            name="intake",
            role="source-bound fact intake",
            model="gemini-3.5-flash",
            deterministic=False,
        ),
        AgentRegistration(
            name="policy",
            role="missing and conflict checks",
            model="gemini-3.5-flash",
            deterministic=False,
        ),
        AgentRegistration(
            name="verifier", role="canonical SHA-256 binding", deterministic=True
        ),
        AgentRegistration(
            name="supervisor",
            role="fail-closed routing and human boundary",
            model="gemini-3.5-flash",
            deterministic=False,
        ),
    ]


@app.post("/cases", response_model=EvidenceCaseResult, status_code=201)
def run_case(
    payload: EvidenceCaseCreate, result_store: ResultStore = Depends(get_store)
) -> EvidenceCaseResult:
    try:
        return EvidenceFleet(result_store).run(payload)
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


@app.post("/cases/{case_id}/brief", response_model=AgentBrief)
async def generate_brief(
    case_id: str,
    result_store: ResultStore = Depends(get_store),
    service: AdkBriefService = Depends(get_brief_service),
) -> AgentBrief:
    result = result_store.get(case_id)
    if result is None:
        raise HTTPException(status_code=404, detail="case not found")
    try:
        return await service.generate(result)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


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
