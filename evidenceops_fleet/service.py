from datetime import datetime, timezone

from opentelemetry import trace

from .models import AgentTrace, EvidenceCaseCreate, EvidenceCaseResult
from .policy import canonical_digest, inspect_evidence
from .store import ResultStore


tracer = trace.get_tracer("evidenceops_fleet")


class EvidenceFleet:
    """Run deterministic specialist agents under a fail-closed supervisor."""

    def __init__(self, store: ResultStore) -> None:
        self.store = store

    def run(self, payload: EvidenceCaseCreate) -> EvidenceCaseResult:
        with tracer.start_as_current_span("evidence_case") as span:
            span.set_attribute("evidenceops.case_id", payload.case_id)
            span.set_attribute("evidenceops.evidence_count", len(payload.evidence))
            return self._run(payload, span)

    def _run(self, payload: EvidenceCaseCreate, span) -> EvidenceCaseResult:
        existing = self.store.get(payload.case_id)
        digest = canonical_digest(payload)
        if existing is not None:
            if existing.evidence_digest != digest:
                span.set_attribute("evidenceops.outcome", "idempotency_conflict")
                raise ValueError("case_id already binds different evidence")
            span.set_attribute("evidenceops.outcome", "idempotent_replay")
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
        span.set_attribute("evidenceops.missing_count", len(missing))
        span.set_attribute("evidenceops.conflict_count", len(conflicts))
        span.set_attribute("evidenceops.outcome", "blocked" if blocked else "ready")
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
