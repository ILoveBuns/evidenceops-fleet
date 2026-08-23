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


def test_dashboard_exposes_synthetic_label_and_three_failure_paths() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "SYNTHETIC DEMO" in response.text
    assert "Missing test receipt" in response.text
    assert "Conflicting source commits" in response.text
