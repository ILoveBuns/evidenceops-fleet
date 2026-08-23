from __future__ import annotations

from os import getenv
from threading import RLock
from typing import Protocol

from .models import ApprovalReceipt, EvidenceCaseResult


class ResultStore(Protocol):
    def save_once(self, result: EvidenceCaseResult) -> EvidenceCaseResult: ...

    def get(self, case_id: str) -> EvidenceCaseResult | None: ...

    def save_approval_once(self, receipt: ApprovalReceipt) -> ApprovalReceipt: ...

    def get_approval(self, case_id: str, approval_id: str) -> ApprovalReceipt | None: ...


class MemoryResultStore:
    """Thread-safe local store used for tests and the zero-credential demo."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceCaseResult] = {}
        self._approvals: dict[tuple[str, str], ApprovalReceipt] = {}
        self._lock = RLock()

    def save_once(self, result: EvidenceCaseResult) -> EvidenceCaseResult:
        with self._lock:
            existing = self._items.get(result.case_id)
            if existing is not None:
                if existing.evidence_digest != result.evidence_digest:
                    raise ValueError("case_id already binds different evidence")
                return existing
            self._items[result.case_id] = result
            return result

    def get(self, case_id: str) -> EvidenceCaseResult | None:
        with self._lock:
            return self._items.get(case_id)

    def save_approval_once(self, receipt: ApprovalReceipt) -> ApprovalReceipt:
        with self._lock:
            key = (receipt.case_id, receipt.approval_id)
            existing = self._approvals.get(key)
            if existing is not None:
                if (
                    existing.actor_digest != receipt.actor_digest
                    or existing.note_digest != receipt.note_digest
                    or existing.evidence_digest != receipt.evidence_digest
                ):
                    raise ValueError("approval_id already binds different approval data")
                return existing
            self._approvals[key] = receipt
            return receipt

    def get_approval(self, case_id: str, approval_id: str) -> ApprovalReceipt | None:
        with self._lock:
            return self._approvals.get((case_id, approval_id))


class FirestoreResultStore:
    """Persist immutable case outcomes with a Firestore transaction."""

    def __init__(self, collection: str = "evidence_cases") -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = firestore.Client()
        self._collection = self._client.collection(collection)

    def save_once(self, result: EvidenceCaseResult) -> EvidenceCaseResult:
        reference = self._collection.document(result.case_id)
        transaction = self._client.transaction()

        @self._firestore.transactional
        def persist(transaction):
            snapshot = reference.get(transaction=transaction)
            if snapshot.exists:
                existing = EvidenceCaseResult.model_validate(snapshot.to_dict())
                if existing.evidence_digest != result.evidence_digest:
                    raise ValueError("case_id already binds different evidence")
                return existing
            transaction.create(reference, result.model_dump(mode="json"))
            return result

        return persist(transaction)

    def get(self, case_id: str) -> EvidenceCaseResult | None:
        snapshot = self._collection.document(case_id).get()
        return EvidenceCaseResult.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def save_approval_once(self, receipt: ApprovalReceipt) -> ApprovalReceipt:
        reference = (
            self._collection.document(receipt.case_id)
            .collection("approvals")
            .document(receipt.approval_id)
        )
        transaction = self._client.transaction()

        @self._firestore.transactional
        def persist(transaction):
            snapshot = reference.get(transaction=transaction)
            if snapshot.exists:
                existing = ApprovalReceipt.model_validate(snapshot.to_dict())
                if (
                    existing.actor_digest != receipt.actor_digest
                    or existing.note_digest != receipt.note_digest
                    or existing.evidence_digest != receipt.evidence_digest
                ):
                    raise ValueError("approval_id already binds different approval data")
                return existing
            transaction.create(reference, receipt.model_dump(mode="json"))
            return receipt

        return persist(transaction)

    def get_approval(self, case_id: str, approval_id: str) -> ApprovalReceipt | None:
        snapshot = (
            self._collection.document(case_id)
            .collection("approvals")
            .document(approval_id)
            .get()
        )
        return ApprovalReceipt.model_validate(snapshot.to_dict()) if snapshot.exists else None


def configured_store() -> ResultStore:
    """Select Firestore explicitly in Cloud Run; never silently claim persistence."""
    if getenv("EVIDENCEOPS_STORE") == "firestore":
        return FirestoreResultStore()
    return MemoryResultStore()
