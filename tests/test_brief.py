import asyncio

from google.adk.events import Event
from google.genai import types

from evidenceops_fleet.brief import AdkBriefService
from evidenceops_fleet.main import app, get_brief_service, get_store
from evidenceops_fleet.models import AgentBrief, EvidenceCaseResult
from evidenceops_fleet.store import MemoryResultStore
from fastapi.testclient import TestClient


class FakeSessionService:
    def __init__(self) -> None:
        self.created = []

    async def create_session(self, **kwargs):
        self.created.append(kwargs)


class FakeRunner:
    calls = 0

    def __init__(self) -> None:
        self.session_service = FakeSessionService()
        self.prompt = ""

    async def run_async(self, **kwargs):
        type(self).calls += 1
        self.prompt = kwargs["new_message"].parts[0].text
        yield Event(
            author="supervisor_agent",
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Keep the case blocked.")],
            ),
        )


def result() -> EvidenceCaseResult:
    return EvidenceCaseResult.model_validate(
        {
            "case_id": "brief-case-0001",
            "decision": "blocked",
            "evidence_digest": "a" * 64,
            "missing": ["tests"],
            "conflicts": [],
            "next_action": "Attach a test receipt",
            "traces": [
                {"agent": "policy", "outcome": "blocked", "detail": "missing=1"}
            ],
            "created_at": "2026-08-23T00:00:00Z",
        }
    )


def test_adk_service_extracts_final_response_from_redacted_result(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-key")
    runner = FakeRunner()
    service = AdkBriefService(runner_factory=lambda: runner)
    brief = asyncio.run(service.generate(result()))
    assert brief.brief == "Keep the case blocked."
    assert brief.source_decision == "blocked"
    assert brief.source_evidence_digest == "a" * 64
    assert brief.final_author == "supervisor_agent"
    assert brief.event_count == 1
    assert "brief-case-0001" in runner.prompt
    assert "private evidence value" not in runner.prompt
    assert runner.session_service.created


def test_brief_endpoint_fails_closed_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_BRIEF_TOKEN", "test-brief-secret")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    result_store = MemoryResultStore()
    result_store.save_once(result())
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post(
            "/cases/brief-case-0001/brief",
            headers={"x-brief-token": "test-brief-secret"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini credentials are not configured"


def test_brief_endpoint_returns_fake_adk_receipt(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-key")
    monkeypatch.setenv("EVIDENCEOPS_BRIEF_TOKEN", "test-brief-secret")
    result_store = MemoryResultStore()
    result_store.save_once(result())
    service = AdkBriefService(runner_factory=FakeRunner)
    FakeRunner.calls = 0
    app.dependency_overrides[get_store] = lambda: result_store
    app.dependency_overrides[get_brief_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.post(
            "/cases/brief-case-0001/brief",
            headers={"x-brief-token": "test-brief-secret"},
        )
        retry = client.post(
            "/cases/brief-case-0001/brief",
            headers={"x-brief-token": "test-brief-secret"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert retry.json() == response.json()
    assert FakeRunner.calls == 1
    assert response.json()["model"] == "gemini-3.5-flash"
    assert response.json()["brief"] == "Keep the case blocked."


def test_brief_endpoint_rejects_unauthorized_paid_call(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-key")
    monkeypatch.setenv("EVIDENCEOPS_BRIEF_TOKEN", "test-brief-secret")
    result_store = MemoryResultStore()
    result_store.save_once(result())
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post("/cases/brief-case-0001/brief")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "brief authorization required"


def test_explicit_public_demo_allows_only_demo_case(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-key")
    monkeypatch.setenv("EVIDENCEOPS_PUBLIC_DEMO_BRIEFS", "true")
    demo_result = result().model_copy(update={"case_id": "demo-brief-case-0001"})
    result_store = MemoryResultStore()
    result_store.save_once(demo_result)
    result_store.save_once(result())
    service = AdkBriefService(runner_factory=FakeRunner)
    app.dependency_overrides[get_store] = lambda: result_store
    app.dependency_overrides[get_brief_service] = lambda: service
    try:
        client = TestClient(app)
        demo_response = client.post("/cases/demo-brief-case-0001/brief")
        real_response = client.post("/cases/brief-case-0001/brief")
    finally:
        app.dependency_overrides.clear()
    assert demo_response.status_code == 200
    assert real_response.status_code == 403


def test_memory_store_rejects_brief_for_different_evidence() -> None:
    result_store = MemoryResultStore()
    first = AgentBrief(
        case_id="brief-case-0001",
        source_decision="blocked",
        source_evidence_digest="a" * 64,
        model="gemini-3.5-flash",
        brief="Keep the case blocked.",
        final_author="supervisor_agent",
        event_count=1,
    )
    changed = first.model_copy(update={"source_evidence_digest": "b" * 64})
    assert result_store.save_brief_once(first) == first
    try:
        result_store.save_brief_once(changed)
    except ValueError as error:
        assert str(error) == "case brief binds different source evidence"
    else:
        raise AssertionError("changed evidence must not reuse a cached brief")
