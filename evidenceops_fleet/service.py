from datetime import datetime, timezone

from .models import AgentTrace, EvidenceCaseCreate, EvidenceCaseResult
from .policy import canonical_digest, inspect_evidence
from .store import ResultStore


class EvidenceFleet:
    """Run deterministic specialist agents under a fail-closed supervisor."""

    def __init__(self, store: ResultStore) -> None:
        self.store = store

    def run(self, payload: EvidenceCaseCreate) -> EvidenceCaseResult:
        existing = self.store.get(payload.case_id)
        digest = canonical_digest(payload)
        if existing is not None:
            if existing.evidence_digest != digest:
                raise ValueError("case_id already binds different evidence")
            return existing

        traces = [
            AgentTrace(
                agent="intake",
                outcome="accepted",
                detail=f"Received {len(payload.evidence)} source-attributed evidence items.",
            )
        ]
        missing, conflicts = inspect_evidence(payload)
        traces.append(
            AgentTrace(
                agent="policy",
                outcome="blocked" if missing or conflicts else "passed",
                detail=f"missing={len(missing)} conflicts={len(conflicts)}",
            )
        )
        traces.append(
            AgentTrace(
                agent="verifier",
                outcome="bound",
                detail=f"SHA-256 {digest}",
            )
        )
        blocked = bool(missing or conflicts)
        result = EvidenceCaseResult(
            case_id=payload.case_id,
            decision="blocked" if blocked else "ready",
            evidence_digest=digest,
            missing=missing,
            conflicts=conflicts,
            next_action=(
                "Resolve missing or conflicting evidence before external action"
                if blocked
                else "Request human approval for the bounded external action"
            ),
            traces=traces,
            created_at=datetime.now(timezone.utc),
        )
        return self.store.save_once(result)

