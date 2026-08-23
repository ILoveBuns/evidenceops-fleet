import hashlib
import json

from .models import EvidenceCaseCreate


def canonical_digest(payload: EvidenceCaseCreate) -> str:
    """Bind the decision to sorted, source-attributed evidence."""
    canonical = [item.model_dump() for item in payload.evidence]
    canonical.sort(key=lambda item: (item["name"], item["source"], item["value"]))
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def inspect_evidence(payload: EvidenceCaseCreate) -> tuple[list[str], list[str]]:
    """Return missing fields and source-visible conflicts without model inference."""
    grouped: dict[str, set[str]] = {}
    for item in payload.evidence:
        grouped.setdefault(item.name, set()).add(item.value.strip())
    missing = sorted(name for name in payload.required_evidence if not grouped.get(name))
    conflicts = sorted(name for name, values in grouped.items() if len(values) > 1)
    return missing, conflicts

