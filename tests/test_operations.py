from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable

from evidenceops_fleet import operations
from evidenceops_fleet import main as main_module
from evidenceops_fleet.main import app, get_store
from evidenceops_fleet.models import EvidenceCaseCreate
from evidenceops_fleet.store import MemoryResultStore


def case_payload() -> dict:
    return {
        "case_id": "operation-0001",
        "objective": "Verify release evidence asynchronously before publication",
        "required_evidence": ["commit", "tests"],
        "evidence": [
            {
                "name": "commit",
                "value": "abc123",
                "source": "https://example.test/commit",
            },
            {
                "name": "tests",
                "value": "22 passed",
                "source": "https://example.test/run",
            },
        ],
    }


def test_local_operation_completes_and_exposes_only_bound_result() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        created = client.post("/operations", json=case_payload())
        fetched = client.get("/operations/operation-operation-0001")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "ready"
    assert fetched.json()["decision"] == "ready"
    assert "abc123" not in fetched.text
    assert "example.test" not in fetched.text


def test_operation_retry_is_idempotent_and_changed_payload_conflicts() -> None:
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        first = client.post("/operations", json=case_payload())
        retry = client.post("/operations", json=case_payload())
        changed = case_payload()
        changed["evidence"][0]["value"] = "different"
        conflict = client.post("/operations", json=changed)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == retry.status_code == 202
    assert retry.json()["input_digest"] == first.json()["input_digest"]
    assert conflict.status_code == 409


def test_cloud_configuration_failure_does_not_persist_operation(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.delenv("EVIDENCEOPS_WORKER_URL", raising=False)
    monkeypatch.delenv("EVIDENCEOPS_TASK_TOKEN", raising=False)
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post("/operations", json=case_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert result_store.get_operation("operation-operation-0001") is None


def test_firestore_mode_refuses_local_background_fallback(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_STORE", "firestore")
    monkeypatch.delenv("EVIDENCEOPS_TASKS_QUEUE", raising=False)
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post("/operations", json=case_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Cloud Tasks configuration is required with Firestore"
    )
    assert result_store.get_operation("operation-operation-0001") is None


def test_invalid_cloud_configuration_does_not_persist_operation(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "not-a-resource-name")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "http://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "short")
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post("/operations", json=case_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert result_store.get_operation("operation-operation-0001") is None


def test_cloud_task_contains_deterministic_name_and_private_worker_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test/")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    captured: dict = {}
    monkeypatch.setattr(
        operations,
        "create_cloud_task",
        lambda parent, task: captured.update(parent=parent, task=task),
    )
    payload = EvidenceCaseCreate.model_validate(case_payload())
    operation = operations.queued_operation(payload)

    operations.enqueue_cloud_task(operation, payload)

    assert captured["parent"] == "projects/p/locations/r/queues/q"
    task = captured["task"]
    assert task["name"].endswith(
        "/tasks/operation-operation-0001-attempt-1"
    )
    assert task["http_request"]["url"] == (
        "https://worker.example.test/operations/operation-operation-0001/execute"
    )
    assert task["http_request"]["headers"]["X-Task-Token"] == "private-task-token"
    assert b"abc123" in task["http_request"]["body"]


def test_cloud_api_failure_becomes_retryable_runtime_error(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    monkeypatch.setattr(
        operations,
        "create_cloud_task",
        lambda parent, task: (_ for _ in ()).throw(ServiceUnavailable("offline")),
    )
    payload = EvidenceCaseCreate.model_validate(case_payload())

    try:
        operations.enqueue_cloud_task(operations.queued_operation(payload), payload)
    except RuntimeError as error:
        assert str(error) == "Cloud Tasks dispatch failed"
    else:
        raise AssertionError("dispatch failure was not mapped")


def test_queued_operation_is_redispatched_after_transient_failure(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    attempts = 0

    def dispatch(operation, payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Cloud Tasks dispatch failed")

    monkeypatch.setattr(main_module, "enqueue_cloud_task", dispatch)
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        failed = client.post("/operations", json=case_payload())
        retried = client.post("/operations", json=case_payload())
    finally:
        app.dependency_overrides.clear()

    assert failed.status_code == 503
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert attempts == 2


def test_failed_operation_dispatches_a_new_deterministic_attempt(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    task_names: list[str] = []

    def capture_task(parent, task):
        task_names.append(task["name"])

    monkeypatch.setattr(operations, "create_cloud_task", capture_task)
    result_store = MemoryResultStore()
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        first = client.post("/operations", json=case_payload())
        operation = result_store.get_operation("operation-operation-0001")
        assert operation is not None
        result_store.update_operation(
            operation.model_copy(update={"status": "failed", "attempt_count": 1})
        )
        retry = client.post("/operations", json=case_payload())
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == retry.status_code == 202
    assert task_names[0].endswith("-attempt-1")
    assert task_names[1].endswith("-attempt-2")


def test_cloud_worker_rejects_wrong_token_and_changed_payload(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    result_store = MemoryResultStore()
    payload = EvidenceCaseCreate.model_validate(case_payload())
    operation = result_store.save_operation_once(operations.queued_operation(payload))
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        client = TestClient(app)
        unauthorized = client.post(
            f"/operations/{operation.operation_id}/execute", json=case_payload()
        )
        changed = case_payload()
        changed["evidence"][0]["value"] = "different"
        mismatch = client.post(
            f"/operations/{operation.operation_id}/execute",
            headers={"x-task-token": "private-task-token"},
            json=changed,
        )
    finally:
        app.dependency_overrides.clear()

    assert unauthorized.status_code == 403
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"] == "operation payload does not match bound evidence"


def test_worker_token_is_enforced_before_queue_configuration(monkeypatch) -> None:
    monkeypatch.delenv("EVIDENCEOPS_TASKS_QUEUE", raising=False)
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    result_store = MemoryResultStore()
    payload = EvidenceCaseCreate.model_validate(case_payload())
    operation = result_store.save_operation_once(operations.queued_operation(payload))
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post(
            f"/operations/{operation.operation_id}/execute", json=case_payload()
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "task authorization required"


def test_active_execution_lease_rejects_duplicate_worker(monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCEOPS_TASKS_QUEUE", "projects/p/locations/r/queues/q")
    monkeypatch.setenv("EVIDENCEOPS_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("EVIDENCEOPS_TASK_TOKEN", "private-task-token")
    result_store = MemoryResultStore()
    payload = EvidenceCaseCreate.model_validate(case_payload())
    operation = result_store.save_operation_once(operations.queued_operation(payload))
    claimed, acquired = result_store.claim_operation(
        operation.operation_id,
        operation.input_digest,
        datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    app.dependency_overrides[get_store] = lambda: result_store
    try:
        response = TestClient(app).post(
            f"/operations/{operation.operation_id}/execute",
            headers={"x-task-token": "private-task-token"},
            json=case_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert acquired is True
    assert claimed.attempt_count == 1
    assert response.status_code == 503
    assert response.json()["detail"] == "operation execution lease is active"


def test_expired_execution_lease_is_reclaimed() -> None:
    result_store = MemoryResultStore()
    payload = EvidenceCaseCreate.model_validate(case_payload())
    operation = result_store.save_operation_once(operations.queued_operation(payload))
    expired = operation.model_copy(
        update={
            "status": "running",
            "attempt_count": 1,
            "lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
    )
    result_store.update_operation(expired)

    completed = operations.process_operation(expired, payload, result_store)

    assert completed.status == "ready"
    assert completed.attempt_count == 2
    assert completed.lease_expires_at is None
from datetime import datetime, timedelta, timezone
