from __future__ import annotations

from os import getenv
from threading import RLock
from typing import Protocol

from .models import EvidenceCaseResult


class ResultStore(Protocol):
    def save_once(self, result: EvidenceCaseResult) -> EvidenceCaseResult: ...

    def get(self, case_id: str) -> EvidenceCaseResult | None: ...


class MemoryResultStore:
    """Thread-safe local store used for tests and the zero-credential demo."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceCaseResult] = {}
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


def configured_store() -> ResultStore:
    """Select Firestore explicitly in Cloud Run; never silently claim persistence."""
    if getenv("EVIDENCEOPS_STORE") == "firestore":
        return FirestoreResultStore()
    return MemoryResultStore()

