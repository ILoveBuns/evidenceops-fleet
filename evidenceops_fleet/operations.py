from __future__ import annotations

import hmac
import re
from datetime import datetime, timedelta, timezone
from os import getenv

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError

from .models import EvidenceCaseCreate, EvidenceOperation
from .policy import canonical_digest
from .service import EvidenceFleet
from .store import ResultStore


class OperationBusyError(RuntimeError):
    pass


def operation_id(payload: EvidenceCaseCreate) -> str:
    return f"operation-{payload.case_id}"


def task_id(operation: EvidenceOperation) -> str:
    return f"{operation.operation_id}-attempt-{operation.attempt_count + 1}"


def queued_operation(payload: EvidenceCaseCreate) -> EvidenceOperation:
    now = datetime.now(timezone.utc)
    return EvidenceOperation(
        operation_id=operation_id(payload),
        case_id=payload.case_id,
        input_digest=canonical_digest(payload),
        status="queued",
        created_at=now,
        updated_at=now,
    )


def process_operation(
    operation: EvidenceOperation,
    payload: EvidenceCaseCreate,
    result_store: ResultStore,
) -> EvidenceOperation:
    payload_digest = canonical_digest(payload)
    running, claimed = result_store.claim_operation(
        operation.operation_id,
        payload_digest,
        datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    if not claimed:
        if running.status in {"ready", "blocked"}:
            return running
        raise OperationBusyError("operation execution lease is active")
    try:
        result = EvidenceFleet(result_store).run(payload)
    except Exception:
        failed = running.model_copy(
            update={
                "status": "failed",
                "error_code": "execution_failed",
                "lease_expires_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        result_store.update_operation(failed)
        raise
    completed = running.model_copy(
        update={
            "status": result.decision,
            "decision": result.decision,
            "evidence_digest": result.evidence_digest,
            "error_code": None,
            "lease_expires_at": None,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return result_store.update_operation(completed)


def cloud_tasks_config() -> tuple[str, str, str]:
    queue = getenv("EVIDENCEOPS_TASKS_QUEUE")
    worker_url = getenv("EVIDENCEOPS_WORKER_URL")
    task_token = getenv("EVIDENCEOPS_TASK_TOKEN")
    if not queue or not worker_url or not task_token:
        raise RuntimeError("Cloud Tasks runtime is not fully configured")
    if not re.fullmatch(r"projects/[^/]+/locations/[^/]+/queues/[^/]+", queue):
        raise RuntimeError("Cloud Tasks queue must use its canonical resource name")
    if not worker_url.startswith("https://"):
        raise RuntimeError("Cloud Tasks worker URL must use HTTPS")
    if len(task_token) < 16:
        raise RuntimeError("Cloud Tasks worker token is too short")
    return queue, worker_url, task_token


def create_cloud_task(parent: str, task: dict) -> None:
    from google.cloud import tasks_v2

    tasks_v2.CloudTasksClient().create_task(parent=parent, task=task)


def enqueue_cloud_task(operation: EvidenceOperation, payload: EvidenceCaseCreate) -> None:
    from google.cloud import tasks_v2

    queue, worker_url, task_token = cloud_tasks_config()
    task = {
        "name": f"{queue}/tasks/{task_id(operation)}",
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{worker_url.rstrip('/')}/operations/{operation.operation_id}/execute",
            "headers": {
                "Content-Type": "application/json",
                "X-Task-Token": task_token,
            },
            "body": payload.model_dump_json().encode(),
        },
    }
    try:
        create_cloud_task(queue, task)
    except AlreadyExists:
        return
    except GoogleAPICallError as error:
        raise RuntimeError("Cloud Tasks dispatch failed") from error


def task_authorized(supplied_token: str) -> bool:
    configured_token = getenv("EVIDENCEOPS_TASK_TOKEN")
    return bool(configured_token) and hmac.compare_digest(
        supplied_token, configured_token
    )
