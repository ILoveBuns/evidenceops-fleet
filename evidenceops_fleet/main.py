from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .dashboard import DASHBOARD_HTML
from .models import AgentRegistration, EvidenceCaseCreate, EvidenceCaseResult
from .service import EvidenceFleet
from .store import ResultStore, configured_store


app = FastAPI(title="EvidenceOps Fleet", version="0.1.0")
store = configured_store()


def get_store() -> ResultStore:
    return store


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidenceops-fleet"}


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
