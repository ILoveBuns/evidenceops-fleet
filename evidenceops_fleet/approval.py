import hashlib
import json
from datetime import datetime, timezone

from .models import ApprovalCreate, ApprovalReceipt, EvidenceCaseResult


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_receipt(
    case: EvidenceCaseResult, payload: ApprovalCreate, created_at: datetime | None = None
) -> ApprovalReceipt:
    """Create a receipt without persisting the actor label or approval note."""
    if case.decision != "ready":
        raise ValueError("blocked evidence cases cannot be approved")
    timestamp = created_at or datetime.now(timezone.utc)
    actor_digest = digest_text(payload.actor_label)
    note_digest = digest_text(payload.note)
    bound = json.dumps(
        {
            "approval_id": payload.approval_id,
            "case_id": case.case_id,
            "evidence_digest": case.evidence_digest,
            "actor_digest": actor_digest,
            "note_digest": note_digest,
            "created_at": timestamp.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return ApprovalReceipt(
        approval_id=payload.approval_id,
        case_id=case.case_id,
        evidence_digest=case.evidence_digest,
        actor_digest=actor_digest,
        note_digest=note_digest,
        receipt_digest=digest_text(bound),
        created_at=timestamp,
    )
