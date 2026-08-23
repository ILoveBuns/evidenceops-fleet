from fastapi.testclient import TestClient

from evidenceops_fleet.main import app, get_store
from evidenceops_fleet.store import MemoryResultStore


def case_payload():
    return {
        "case_id": "release-0001",
        "objective": "Verify the release before publication",
        "required_evidence": ["commit", "tests"],
        "evidence": [
            {"name": "commit", "value": "abc123", "source": "https://example.test/commit"},
            {"name": "tests", "value": "17 passed", "source": "https://example.test/run"},
        ],
    }


def test_complete_case_is_ready_and_persisted() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        created = client.post("/cases", json=case_payload())
        fetched = client.get("/cases/release-0001")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert created.json()["decision"] == "ready"
    assert fetched.json() == created.json()
    assert [trace["agent"] for trace in created.json()["traces"]] == [
        "intake",
        "policy",
        "verifier",
    ]


def test_missing_evidence_fails_closed() -> None:
    payload = case_payload()
    payload["evidence"].pop()
    app.dependency_overrides[get_store] = MemoryResultStore
    try:
        result = TestClient(app).post("/cases", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert result.json()["decision"] == "blocked"
    assert result.json()["missing"] == ["tests"]


def test_case_id_is_idempotent_and_rejects_changed_evidence() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        first = client.post("/cases", json=case_payload())
        retry = client.post("/cases", json=case_payload())
        changed = case_payload()
        changed["evidence"][0]["value"] = "different"
        conflict = client.post("/cases", json=changed)
    finally:
        app.dependency_overrides.clear()
    assert retry.json() == first.json()
    assert conflict.status_code == 409


def test_agent_registry_discloses_gemini_and_deterministic_roles() -> None:
    response = TestClient(app).get("/agents")
    assert response.status_code == 200
    assert {item["model"] for item in response.json()} == {None, "gemini-3.5-flash"}


def test_runtime_discloses_capabilities_without_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "private-gemini-key")
    monkeypatch.setenv("EVIDENCEOPS_APPROVAL_TOKEN", "private-approval-token")
    response = TestClient(app).get("/runtime")
    assert response.status_code == 200
    assert response.json() == {
        "store": "memory",
        "gemini_ready": True,
        "approval_guard": "secret",
    }
    assert "private-gemini-key" not in response.text
    assert "private-approval-token" not in response.text


def test_dashboard_exposes_synthetic_label_and_three_failure_paths() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "SYNTHETIC DEMO" in response.text
    assert "Missing test receipt" in response.text
    assert "Conflicting source commits" in response.text
    assert "Human approve ready case" in response.text
    assert "Generate Gemini brief" in response.text
    assert "Runtime disclosure" in response.text


def test_ready_case_can_be_approved_without_persisting_raw_identity() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        case = case_payload()
        case["case_id"] = "demo-ready-0001"
        client.post("/cases", json=case)
        payload = {
            "approval_id": "approval-0001",
            "actor_label": "synthetic-demo-reviewer",
            "note": "Reviewed commit, tests, and artifact receipts",
        }
        first = client.post("/cases/demo-ready-0001/approvals", json=payload)
        retry = client.post("/cases/demo-ready-0001/approvals", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    serialized = first.text
    assert "synthetic-demo-reviewer" not in serialized
    assert "Reviewed commit" not in serialized


def test_blocked_case_cannot_be_approved() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        payload = case_payload()
        payload["case_id"] = "demo-blocked-0001"
        payload["evidence"].pop()
        client.post("/cases", json=payload)
        response = client.post(
            "/cases/demo-blocked-0001/approvals",
            json={
                "approval_id": "approval-blocked",
                "actor_label": "synthetic-demo-reviewer",
                "note": "Attempted approval despite missing evidence",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"] == "blocked evidence cases cannot be approved"


def test_non_demo_approval_requires_authorization() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        client.post("/cases", json=case_payload())
        response = client.post(
            "/cases/release-0001/approvals",
            json={
                "approval_id": "approval-real-1",
                "actor_label": "Release manager",
                "note": "Reviewed all evidence before approval",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_authorized_real_approval_uses_secret_header(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_APPROVAL_TOKEN", "test-approval-secret")
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        client.post("/cases", json=case_payload())
        response = client.post(
            "/cases/release-0001/approvals",
            headers={"x-approval-token": "test-approval-secret"},
            json={
                "approval_id": "approval-real-2",
                "actor_label": "Release manager",
                "note": "Reviewed all evidence before approval",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert "test-approval-secret" not in response.text
